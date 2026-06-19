"""并发优化模块 — 异步处理、连接池、上下文窗口管理"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class TaskResult:
    task_id: str
    result: Any = None
    error: Optional[str] = None
    latency_ms: float = 0.0
    success: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ContextWindow:
    max_tokens: int = 4000
    current_tokens: int = 0
    history: deque = field(default_factory=lambda: deque(maxlen=100))

    @property
    def remaining_tokens(self) -> int:
        return self.max_tokens - self.current_tokens

    @property
    def is_full(self) -> bool:
        return self.current_tokens >= self.max_tokens


@dataclass
class ConnectionPool:
    max_connections: int = 10
    active_connections: int = 0
    waiting_queue: deque = field(default_factory=deque)

    @property
    def available(self) -> bool:
        return self.active_connections < self.max_connections

    @property
    def utilization(self) -> float:
        return self.active_connections / self.max_connections if self.max_connections > 0 else 0


class ConcurrencyOptimizer:
    """并发优化器"""

    def __init__(self, max_concurrent: int = 10, max_context_tokens: int = 4000):
        self.config = get_config()
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._connection_pool = ConnectionPool(max_connections=max_concurrent)
        self._context_windows: dict[str, ContextWindow] = {}
        self._task_counter = 0
        self._max_context_tokens = max_context_tokens

    async def execute_with_limit(self, func: Callable, *args, **kwargs) -> TaskResult:
        """带并发限制地执行任务"""
        task_id = f"task_{self._task_counter}"
        self._task_counter += 1

        start = time.monotonic()
        async with self._semaphore:
            self._connection_pool.active_connections += 1
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                latency = (time.monotonic() - start) * 1000
                return TaskResult(
                    task_id=task_id,
                    result=result,
                    latency_ms=latency,
                    success=True,
                )
            except Exception as e:
                latency = (time.monotonic() - start) * 1000
                return TaskResult(
                    task_id=task_id,
                    error=str(e),
                    latency_ms=latency,
                    success=False,
                )
            finally:
                self._connection_pool.active_connections -= 1

    async def execute_batch(self, tasks: list[Callable]) -> list[TaskResult]:
        """批量执行任务"""
        results = []
        for task in tasks:
            result = await self.execute_with_limit(task)
            results.append(result)
        return results

    async def execute_parallel(self, tasks: list[Callable]) -> list[TaskResult]:
        """并行执行任务"""
        coros = [self.execute_with_limit(task) for task in tasks]
        return await asyncio.gather(*coros)

    def get_context_window(self, session_id: str = "default") -> ContextWindow:
        """获取上下文窗口"""
        if session_id not in self._context_windows:
            self._context_windows[session_id] = ContextWindow(
                max_tokens=self._max_context_tokens
            )
        return self._context_windows[session_id]

    def add_to_context(self, content: str, tokens: int, session_id: str = "default") -> bool:
        """添加内容到上下文窗口"""
        window = self.get_context_window(session_id)
        if window.current_tokens + tokens > window.max_tokens:
            overflow = window.current_tokens + tokens - window.max_tokens
            removed = 0
            while removed < overflow and window.history:
                old_tokens = window.history.popleft()
                removed += old_tokens
                window.current_tokens -= old_tokens

        window.history.append(tokens)
        window.current_tokens += tokens
        return True

    def get_context_summary(self, session_id: str = "default") -> dict:
        """获取上下文摘要"""
        window = self.get_context_window(session_id)
        return {
            "max_tokens": window.max_tokens,
            "current_tokens": window.current_tokens,
            "remaining_tokens": window.remaining_tokens,
            "is_full": window.is_full,
            "history_length": len(window.history),
        }

    def truncate_context(self, content: str, max_tokens: int) -> str:
        """截断上下文到指定token数"""
        estimated_tokens = len(content) * 2
        if estimated_tokens <= max_tokens:
            return content

        chars_for_tokens = max_tokens // 2
        return content[:chars_for_tokens] + "..."

    def optimize_messages(self, messages: list[dict], max_tokens: int = 4000) -> list[dict]:
        """优化消息列表以适应上下文窗口"""
        total_tokens = 0
        optimized = []

        for msg in reversed(messages):
            msg_tokens = len(msg.get("content", "")) * 2
            if total_tokens + msg_tokens > max_tokens:
                break
            total_tokens += msg_tokens
            optimized.append(msg)

        optimized.reverse()
        return optimized

    def get_pool_stats(self) -> dict:
        """获取连接池统计"""
        return {
            "max_connections": self._connection_pool.max_connections,
            "active_connections": self._connection_pool.active_connections,
            "utilization": self._connection_pool.utilization,
            "available": self._connection_pool.available,
        }

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "task_counter": self._task_counter,
            "context_windows": len(self._context_windows),
            "pool": self.get_pool_stats(),
        }
