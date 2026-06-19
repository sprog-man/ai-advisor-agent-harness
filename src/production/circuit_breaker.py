"""熔断机制模块 — 错误率/响应时间熔断"""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # 正常（允许请求）
    OPEN = "open"           # 熔断（拒绝请求）
    HALF_OPEN = "half_open" # 半开（试探性允许）


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # 失败次数阈值
    success_threshold: int = 3  # 半开状态成功次数阈值
    timeout_seconds: float = 30.0  # 熔断超时时间
    failure_rate_threshold: float = 0.5  # 失败率阈值
    latency_threshold_ms: float = 2000.0  # 延迟阈值
    window_size: int = 10  # 滑动窗口大小


@dataclass
class CircuitStats:
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[str] = None
    avg_latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class CircuitBreaker:
    """熔断器"""

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._window: list[bool] = []  # 滑动窗口
        self._opened_at: Optional[float] = None
        self._half_open_successes = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and self._opened_at:
            if time.monotonic() - self._opened_at >= self.config.timeout_seconds:
                self._state = CircuitState.HALF_OPEN
                self._half_open_successes = 0
                logger.info("熔断器进入半开状态")
        return self._state

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """通过熔断器执行函数"""
        current_state = self.state

        if current_state == CircuitState.OPEN:
            logger.warning("熔断器开启，拒绝请求")
            raise CircuitBreakerOpenError("熔断器已开启，请求被拒绝")

        start = time.monotonic()
        try:
            result = await func(*args, **kwargs) if callable(func) and hasattr(func, '__call__') else func(*args, **kwargs)
            latency_ms = (time.monotonic() - start) * 1000

            if latency_ms > self.config.latency_threshold_ms:
                self._record_failure(latency_ms)
            else:
                self._record_success(latency_ms)

            return result
        except Exception as e:
            latency_ms = (time.monotonic() - start) * 1000
            self._record_failure(latency_ms)
            raise

    def _record_success(self, latency_ms: float):
        """记录成功"""
        self._stats.total_requests += 1
        self._stats.success_count += 1
        self._stats.consecutive_failures = 0
        self._stats.consecutive_successes += 1

        self._update_avg_latency(latency_ms)
        self._window.append(True)
        if len(self._window) > self.config.window_size:
            self._window.pop(0)

        if self._state == CircuitState.HALF_OPEN:
            self._half_open_successes += 1
            if self._half_open_successes >= self.config.success_threshold:
                self._state = CircuitState.CLOSED
                self._window.clear()
                logger.info("熔断器恢复正常")

    def _record_failure(self, latency_ms: float):
        """记录失败"""
        self._stats.total_requests += 1
        self._stats.failure_count += 1
        self._stats.consecutive_failures += 1
        self._stats.consecutive_successes = 0
        self._stats.last_failure_time = datetime.now().isoformat()

        self._update_avg_latency(latency_ms)
        self._window.append(False)
        if len(self._window) > self.config.window_size:
            self._window.pop(0)

        if self._should_trip():
            self._trip()

    def _update_avg_latency(self, latency_ms: float):
        """更新平均延迟"""
        total = self._stats.total_requests
        self._stats.avg_latency_ms = (
            (self._stats.avg_latency_ms * (total - 1) + latency_ms) / total
        )

    def _should_trip(self) -> bool:
        """判断是否应该触发熔断"""
        if self._state == CircuitState.HALF_OPEN:
            return True

        if self._stats.consecutive_failures >= self.config.failure_threshold:
            return True

        if len(self._window) >= self.config.window_size:
            failure_count = sum(1 for r in self._window if not r)
            failure_rate = failure_count / len(self._window)
            if failure_rate >= self.config.failure_rate_threshold:
                return True

        return False

    def _trip(self):
        """触发熔断"""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning("熔断器触发: consecutive_failures=%d", self._stats.consecutive_failures)

    def reset(self):
        """重置熔断器"""
        self._state = CircuitState.CLOSED
        self._stats = CircuitStats()
        self._window.clear()
        self._opened_at = None
        self._half_open_successes = 0
        logger.info("熔断器已重置")

    def get_stats(self) -> CircuitStats:
        """获取统计信息"""
        return self._stats

    def get_state(self) -> CircuitState:
        """获取当前状态"""
        return self.state

    def force_open(self):
        """强制开启熔断"""
        self._state = CircuitState.OPEN
        self._opened_at = time.monotonic()
        logger.warning("熔断器强制开启")

    def force_close(self):
        """强制关闭熔断"""
        self._state = CircuitState.CLOSED
        self._opened_at = None
        logger.info("熔断器强制关闭")


class CircuitBreakerOpenError(Exception):
    """熔断器开启异常"""
    pass
