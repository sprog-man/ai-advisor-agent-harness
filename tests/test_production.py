"""灰度测试与熔断机制测试"""

import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.production.gray_test import GrayTest, GrayTestConfig, DeploymentStage, ShadowComparison
from src.production.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitState, CircuitBreakerOpenError


class TestGrayTest:
    def setup_method(self):
        self.config = GrayTestConfig(
            stage=DeploymentStage.SHADOW,
            success_threshold=0.9,
            latency_threshold_ms=1000,
            min_samples=5,
        )
        self.gray = GrayTest(self.config)

    @pytest.mark.asyncio
    async def test_shadow_execute(self):
        async def old_handler(x):
            return f"old_{x}"

        async def new_handler(x):
            return f"new_{x}"

        self.gray.set_handlers(old_handler, new_handler)
        result = await self.gray.execute("test")
        assert result == "old_test"
        assert len(self.gray.get_shadow_comparisons()) == 1

    @pytest.mark.asyncio
    async def test_canary_execute(self):
        async def old_handler(x):
            return f"old_{x}"

        async def new_handler(x):
            return f"new_{x}"

        self.gray.set_handlers(old_handler, new_handler)
        self.gray.config.stage = DeploymentStage.CANARY
        self.gray.config.traffic_percent = 100

        results = set()
        for _ in range(10):
            r = await self.gray.execute("test")
            results.add(r)
        assert len(results) <= 2

    def test_should_rollback_low_success(self):
        self.gray._stats.total_requests = 10
        self.gray._stats.success_count = 5
        assert self.gray.should_rollback() is True

    def test_should_rollback_high_latency(self):
        self.gray._stats.total_requests = 10
        self.gray._stats.success_count = 10
        self.gray._stats.avg_latency_ms = 1500
        assert self.gray.should_rollback() is True

    def test_advance_stage(self):
        self.gray._stats.total_requests = 10
        self.gray._stats.success_count = 10
        self.gray._stats.success_rate = 1.0
        self.gray._stats.avg_latency_ms = 100

        stage = self.gray.advance_stage()
        assert stage == DeploymentStage.CANARY

    def test_shadow_comparison(self):
        comparison = ShadowComparison(
            input_data="test",
            old_output="old",
            new_output="new",
            old_latency_ms=100,
            new_latency_ms=150,
            old_success=True,
            new_success=True,
        )
        assert comparison.match is False


class TestCircuitBreaker:
    def setup_method(self):
        self.config = CircuitBreakerConfig(
            failure_threshold=3,
            success_threshold=2,
            timeout_seconds=0.1,
            window_size=5,
        )
        self.breaker = CircuitBreaker(self.config)

    @pytest.mark.asyncio
    async def test_execute_success(self):
        async def func(x):
            return x * 2

        result = await self.breaker.execute(func, 5)
        assert result == 10
        assert self.breaker.get_state() == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_execute_failure(self):
        async def func(x):
            raise ValueError("error")

        with pytest.raises(ValueError):
            await self.breaker.execute(func, 5)
        assert self.breaker._stats.consecutive_failures == 1

    @pytest.mark.asyncio
    async def test_circuit_trip(self):
        async def func(x):
            raise ValueError("error")

        for _ in range(3):
            with pytest.raises(ValueError):
                await self.breaker.execute(func, 5)

        assert self.breaker.get_state() == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_circuit_open_reject(self):
        self.breaker.force_open()

        async def func(x):
            return x

        with pytest.raises(CircuitBreakerOpenError):
            await self.breaker.execute(func, 5)

    @pytest.mark.asyncio
    async def test_circuit_half_open_recovery(self):
        self.breaker.force_open()
        time.sleep(0.15)

        async def func(x):
            return x

        await self.breaker.execute(func, 5)
        await self.breaker.execute(func, 5)
        assert self.breaker.get_state() == CircuitState.CLOSED

    def test_reset(self):
        self.breaker.force_open()
        self.breaker.reset()
        assert self.breaker.get_state() == CircuitState.CLOSED

    def test_stats(self):
        stats = self.breaker.get_stats()
        assert stats.total_requests == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
