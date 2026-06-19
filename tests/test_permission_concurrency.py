"""权限控制与并发优化测试"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.production.permission_control import (
    PermissionControl, Permission, ResourceType, User, Role, AccessContext, AccessResult,
)
from src.production.concurrency_optimizer import ConcurrencyOptimizer, TaskResult, ContextWindow


class TestPermissionControl:
    def setup_method(self):
        self.pc = PermissionControl()
        self.pc.register_user(User(user_id="user1", roles=["user"], rate_limit=10, quota=100))
        self.pc.register_user(User(user_id="viewer1", roles=["viewer"], rate_limit=10, quota=100))
        self.pc.register_user(User(user_id="admin1", roles=["admin"], rate_limit=100, quota=1000))

    @pytest.mark.asyncio
    async def test_check_access_allowed(self):
        context = AccessContext(
            user_id="user1",
            resource_type=ResourceType.CONVERSATION,
            permission=Permission.READ,
        )
        result = await self.pc.check_access(context)
        assert result.allowed is True

    @pytest.mark.asyncio
    async def test_check_access_denied(self):
        context = AccessContext(
            user_id="viewer1",
            resource_type=ResourceType.TOOL,
            permission=Permission.EXECUTE,
        )
        result = await self.pc.check_access(context)
        assert result.allowed is False
        assert "权限不足" in result.reason

    @pytest.mark.asyncio
    async def test_check_access_unknown_user(self):
        context = AccessContext(
            user_id="unknown",
            resource_type=ResourceType.CONVERSATION,
            permission=Permission.READ,
        )
        result = await self.pc.check_access(context)
        assert result.allowed is False
        assert "用户不存在" in result.reason

    def test_get_user_permissions(self):
        perms = self.pc.get_user_permissions("user1")
        assert ResourceType.CONVERSATION in perms
        assert Permission.READ in perms[ResourceType.CONVERSATION]

    def test_admin_has_all_permissions(self):
        perms = self.pc.get_user_permissions("admin1")
        assert len(perms) == 0 or all(Permission.ADMIN in p for p in perms.values())


class TestConcurrencyOptimizer:
    def setup_method(self):
        self.optimizer = ConcurrencyOptimizer(max_concurrent=3, max_context_tokens=100)

    @pytest.mark.asyncio
    async def test_execute_with_limit(self):
        async def func(x):
            return x * 2

        result = await self.optimizer.execute_with_limit(func, 5)
        assert result.success is True
        assert result.result == 10
        assert result.latency_ms >= 0

    @pytest.mark.asyncio
    async def test_execute_with_error(self):
        async def func(x):
            raise ValueError("error")

        result = await self.optimizer.execute_with_limit(func, 5)
        assert result.success is False
        assert "error" in result.error

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        async def func(x):
            return x * 2

        tasks = [lambda: func(i) for i in range(5)]
        results = await self.optimizer.execute_batch(tasks)
        assert len(results) == 5

    def test_context_window(self):
        window = self.optimizer.get_context_window("test")
        assert window.max_tokens == 100
        assert window.remaining_tokens == 100

    def test_add_to_context(self):
        self.optimizer.add_to_context("hello", 50, "test")
        window = self.optimizer.get_context_window("test")
        assert window.current_tokens == 50
        assert window.remaining_tokens == 50

    def test_context_overflow(self):
        for i in range(5):
            self.optimizer.add_to_context(f"msg_{i}", 30, "test")
        window = self.optimizer.get_context_window("test")
        assert window.current_tokens <= window.max_tokens

    def test_truncate_context(self):
        content = "x" * 200
        truncated = self.optimizer.truncate_context(content, 50)
        assert len(truncated) <= 101

    def test_optimize_messages(self):
        messages = [{"content": "x" * 100} for _ in range(10)]
        optimized = self.optimizer.optimize_messages(messages, max_tokens=200)
        assert len(optimized) < 10

    def test_pool_stats(self):
        stats = self.optimizer.get_pool_stats()
        assert stats["max_connections"] == 3
        assert stats["active_connections"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
