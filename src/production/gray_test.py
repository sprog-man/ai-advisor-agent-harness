"""灰度测试模块 — 影子模式、小流量切换、逐步放大"""

import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class DeploymentStage(Enum):
    SHADOW = "shadow"           # 影子模式（只对比不切换）
    CANARY = "canary"           # 金丝雀（小流量）
    PROGRESSIVE = "progressive" # 逐步放大
    FULL = "full"               # 全量发布


@dataclass
class ABTestResult:
    version: str
    input_data: Any
    output: Any
    latency_ms: float
    success: bool
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ShadowComparison:
    input_data: Any
    old_output: Any
    new_output: Any
    old_latency_ms: float
    new_latency_ms: float
    old_success: bool
    new_success: bool
    match: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GrayTestConfig:
    stage: DeploymentStage = DeploymentStage.SHADOW
    traffic_percent: float = 1.0  # 流量百分比
    success_threshold: float = 0.95  # 成功率阈值
    latency_threshold_ms: float = 1000  # 延迟阈值
    min_samples: int = 10  # 最小样本数
    auto_rollback: bool = True  # 自动回滚


@dataclass
class GrayTestStats:
    total_requests: int = 0
    success_count: int = 0
    failure_count: int = 0
    avg_latency_ms: float = 0.0
    success_rate: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class GrayTest:
    """灰度测试管理器"""

    def __init__(self, config: Optional[GrayTestConfig] = None):
        self.config = config or GrayTestConfig()
        self._old_handler: Optional[Callable] = None
        self._new_handler: Optional[Callable] = None
        self._stats = GrayTestStats()
        self._history: list[ABTestResult] = []
        self._shadow_comparisons: list[ShadowComparison] = []

    def set_handlers(self, old_handler: Callable, new_handler: Callable):
        """设置新旧版本处理器"""
        self._old_handler = old_handler
        self._new_handler = new_handler
        logger.info("设置灰度测试处理器")

    async def execute(self, input_data: Any) -> Any:
        """根据当前阶段执行请求"""
        if self.config.stage == DeploymentStage.SHADOW:
            return await self._shadow_execute(input_data)
        elif self.config.stage == DeploymentStage.CANARY:
            return await self._canary_execute(input_data)
        elif self.config.stage == DeploymentStage.PROGRESSIVE:
            return await self._progressive_execute(input_data)
        else:
            return await self._full_execute(input_data)

    async def _shadow_execute(self, input_data: Any) -> Any:
        """影子模式：同时执行新旧版本，返回旧版本结果"""
        if not self._old_handler or not self._new_handler:
            raise ValueError("未设置处理器")

        start_old = time.monotonic()
        try:
            old_output = await self._old_handler(input_data)
            old_success = True
        except Exception as e:
            old_output = str(e)
            old_success = False
        old_latency = (time.monotonic() - start_old) * 1000

        start_new = time.monotonic()
        try:
            new_output = await self._new_handler(input_data)
            new_success = True
        except Exception as e:
            new_output = str(e)
            new_success = False
        new_latency = (time.monotonic() - start_new) * 1000

        comparison = ShadowComparison(
            input_data=input_data,
            old_output=old_output,
            new_output=new_output,
            old_latency_ms=old_latency,
            new_latency_ms=new_latency,
            old_success=old_success,
            new_success=new_success,
            match=(old_output == new_output),
        )
        self._shadow_comparisons.append(comparison)

        self._update_stats(old_success, old_latency)
        logger.debug("影子模式执行: old_latency=%.1fms, new_latency=%.1fms, match=%s", old_latency, new_latency, comparison.match)

        return old_output

    async def _canary_execute(self, input_data: Any) -> Any:
        """金丝雀模式：小流量切换"""
        if random.random() * 100 < self.config.traffic_percent:
            return await self._execute_new(input_data)
        return await self._execute_old(input_data)

    async def _progressive_execute(self, input_data: Any) -> Any:
        """逐步放大模式"""
        return await self._canary_execute(input_data)

    async def _full_execute(self, input_data: Any) -> Any:
        """全量发布"""
        return await self._execute_new(input_data)

    async def _execute_old(self, input_data: Any) -> Any:
        """执行旧版本"""
        start = time.monotonic()
        try:
            output = await self._old_handler(input_data) if self._old_handler else None
            self._update_stats(True, (time.monotonic() - start) * 1000)
            return output
        except Exception as e:
            self._update_stats(False, (time.monotonic() - start) * 1000)
            raise

    async def _execute_new(self, input_data: Any) -> Any:
        """执行新版本"""
        start = time.monotonic()
        try:
            output = await self._new_handler(input_data) if self._new_handler else None
            self._update_stats(True, (time.monotonic() - start) * 1000)
            return output
        except Exception as e:
            self._update_stats(False, (time.monotonic() - start) * 1000)
            raise

    def _update_stats(self, success: bool, latency_ms: float):
        """更新统计"""
        self._stats.total_requests += 1
        if success:
            self._stats.success_count += 1
        else:
            self._stats.failure_count += 1

        total = self._stats.total_requests
        self._stats.avg_latency_ms = (
            (self._stats.avg_latency_ms * (total - 1) + latency_ms) / total
        )
        self._stats.success_rate = self._stats.success_count / total if total > 0 else 0

    def should_rollback(self) -> bool:
        """判断是否需要回滚"""
        if self._stats.total_requests < self.config.min_samples:
            return False

        if self._stats.success_rate < self.config.success_threshold:
            logger.warning("成功率 %.2f 低于阈值 %.2f，建议回滚", self._stats.success_rate, self.config.success_threshold)
            return True

        if self._stats.avg_latency_ms > self.config.latency_threshold_ms:
            logger.warning("平均延迟 %.1fms 超过阈值 %.1fms，建议回滚", self._stats.avg_latency_ms, self.config.latency_threshold_ms)
            return True

        return False

    def advance_stage(self) -> DeploymentStage:
        """自动推进阶段"""
        if self.should_rollback():
            self.config.stage = DeploymentStage.SHADOW
            self.config.traffic_percent = 1.0
            logger.info("回滚到影子模式")
            return self.config.stage

        if self.config.stage == DeploymentStage.SHADOW:
            self.config.stage = DeploymentStage.CANARY
            self.config.traffic_percent = 5.0
        elif self.config.stage == DeploymentStage.CANARY:
            self.config.stage = DeploymentStage.PROGRESSIVE
            self.config.traffic_percent = 50.0
        elif self.config.stage == DeploymentStage.PROGRESSIVE:
            self.config.stage = DeploymentStage.FULL
            self.config.traffic_percent = 100.0

        logger.info("推进到阶段: %s, 流量: %.1f%%", self.config.stage.value, self.config.traffic_percent)
        return self.config.stage

    def get_stats(self) -> GrayTestStats:
        """获取统计信息"""
        return self._stats

    def get_shadow_comparisons(self) -> list[ShadowComparison]:
        """获取影子模式对比结果"""
        return self._shadow_comparisons

    def get_history(self) -> list[ABTestResult]:
        """获取历史结果"""
        return self._history
