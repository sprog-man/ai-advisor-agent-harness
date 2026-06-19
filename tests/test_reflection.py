"""反思机制测试"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.reflection.conflict_detector import ConflictDetector, ConflictDetectionResult, ConflictType
from src.reflection.self_correction import SelfCorrection, CorrectionResult
from src.reflection.agent_debate import AgentDebate, AgentRole, DebateResult
from src.reflection.fallback_handler import FallbackHandler, FallbackTrigger


class TestConflictDetector:
    def setup_method(self):
        self.detector = ConflictDetector()

    @pytest.mark.asyncio
    async def test_detect_no_conflict(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"has_conflict": false, "conflicts": [], "summary": "无冲突"}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.detector, "_build_llm", return_value=mock_llm):
            result = await self.detector.detect("Python是一种编程语言")
            assert result.has_conflict is False
            assert len(result.conflicts) == 0

    @pytest.mark.asyncio
    async def test_detect_with_conflict(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"has_conflict": true, "conflicts": [{"type": "logical", "description": "矛盾", "severity": "high", "involved_items": ["A", "B"], "suggestion": "修改"}], "summary": "存在逻辑矛盾"}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.detector, "_build_llm", return_value=mock_llm):
            result = await self.detector.detect("A是B，A不是B")
            assert result.has_conflict is True
            assert len(result.conflicts) == 1
            assert result.conflicts[0].conflict_type == ConflictType.LOGICAL

    @pytest.mark.asyncio
    async def test_parse_failure(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not json"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.detector, "_build_llm", return_value=mock_llm):
            result = await self.detector.detect("test")
            assert result.has_conflict is False


class TestSelfCorrection:
    def setup_method(self):
        self.correction = SelfCorrection(max_retries=2)

    @pytest.mark.asyncio
    async def test_correct_no_conflict(self):
        conflict_result = ConflictDetectionResult(has_conflict=False, conflicts=[])
        result = await self.correction.correct("测试内容", conflict_result)
        assert result.success is True
        assert result.corrected == "测试内容"

    @pytest.mark.asyncio
    async def test_correct_with_conflict(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "修正后的内容"
        mock_llm.ainvoke.return_value = mock_response

        conflict_result = ConflictDetectionResult(
            has_conflict=True,
            conflicts=[],
        )

        with patch.object(self.correction, "_build_llm", return_value=mock_llm):
            with patch("src.reflection.conflict_detector.ConflictDetector.detect") as mock_detect:
                mock_detect.return_value = ConflictDetectionResult(has_conflict=False, conflicts=[])
                result = await self.correction.correct("原始内容", conflict_result)
                assert result.corrected == "修正后的内容"


class TestAgentDebate:
    def setup_method(self):
        self.debate = AgentDebate(max_rounds=2)

    @pytest.mark.asyncio
    async def test_debate_flow(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "分析结果"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.debate, "_build_llm", return_value=mock_llm):
            result = await self.debate.debate("Python vs Java")
            assert isinstance(result, DebateResult)
            assert result.topic == "Python vs Java"
            assert len(result.opinions) > 0

    @pytest.mark.asyncio
    async def test_consult(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "建议内容"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.debate, "_build_llm", return_value=mock_llm):
            opinion = await self.debate.consult("技术选型", "性能视角")
            assert opinion.role == AgentRole.VALIDATOR


class TestFallbackHandler:
    def setup_method(self):
        self.handler = FallbackHandler()

    def test_should_fallback_max_retries(self):
        trigger = self.handler.should_fallback(retry_count=3)
        assert trigger == FallbackTrigger.MAX_RETRIES

    def test_should_fallback_low_confidence(self):
        trigger = self.handler.should_fallback(retry_count=1, confidence=0.2)
        assert trigger == FallbackTrigger.LOW_CONFIDENCE

    def test_should_fallback_no_trigger(self):
        trigger = self.handler.should_fallback(retry_count=1, confidence=0.8)
        assert trigger is None

    @pytest.mark.asyncio
    async def test_handle_simplify(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "简化内容"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.handler, "_build_llm", return_value=mock_llm):
            result = await self.handler.handle(FallbackTrigger.MAX_RETRIES, "复杂内容")
            assert result.triggered is True
            assert result.output == "简化内容"

    @pytest.mark.asyncio
    async def test_handle_human_intervention_no_callback(self):
        result = await self.handler.handle(FallbackTrigger.CRITICAL_CONFLICT, "冲突内容")
        assert result.needs_human is True
        assert "需要人工介入" in result.output

    @pytest.mark.asyncio
    async def test_handle_with_callback(self):
        async def callback(context, error):
            return "人工处理完成"

        self.handler.set_human_callback(callback)
        result = await self.handler.handle(FallbackTrigger.CRITICAL_CONFLICT, "冲突内容")
        assert result.output == "人工处理完成"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
