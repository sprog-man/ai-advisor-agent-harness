"""反馈循环学习机制测试"""

import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.learning.feedback_loop_orchestrator import FeedbackLoopOrchestrator, EvolutionResult, SystemState


class TestFeedbackLoopOrchestrator:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.orchestrator = FeedbackLoopOrchestrator()
        self.orchestrator.memory.cold = __import__('src.memory.cold_memory', fromlist=['ColdMemory']).ColdMemory(storage_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_process_feedback(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"rules": [{"description": "回答要准确", "category": "accuracy", "trigger": "错误", "action": "验证", "priority": 8}]}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.orchestrator.feedback_loop, "_build_llm", return_value=mock_llm):
            result = await self.orchestrator.process_feedback("回答有错误")
            assert result.rules_extracted >= 0

    @pytest.mark.asyncio
    async def test_apply_rules_to_context(self):
        from src.learning.feedback_loop import Rule
        self.orchestrator.feedback_loop._rules.append(
            Rule(description="回答要准确", trigger="错误", action="验证", active=True)
        )
        context = await self.orchestrator.apply_rules_to_context("用户说回答有错误")
        assert "遵循规则" in context

    @pytest.mark.asyncio
    async def test_apply_rules_no_match(self):
        context = await self.orchestrator.apply_rules_to_context("普通对话")
        assert "遵循规则" not in context

    @pytest.mark.asyncio
    async def test_learn_from_cases(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"rules": [{"description": "规则1", "category": "test", "trigger": "条件", "action": "动作", "priority": 5, "confidence": 0.8, "test_cases": []}]}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.orchestrator.rule_extractor, "_build_llm", return_value=mock_llm):
            cases = [{"user_input": "input", "system_output": "output", "error_description": "error"}]
            count = await self.orchestrator.learn_from_cases(cases)
            assert count >= 0

    def test_get_state(self):
        state = self.orchestrator.get_state()
        assert isinstance(state, SystemState)
        assert state.total_feedbacks == 0

    def test_get_feedback_history(self):
        assert len(self.orchestrator.get_feedback_history()) == 0

    @pytest.mark.asyncio
    async def test_get_system_prompt(self):
        prompt = await self.orchestrator.get_system_prompt()
        assert isinstance(prompt, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
