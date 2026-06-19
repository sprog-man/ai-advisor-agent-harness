"""Bad Case闭环学习测试"""

import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.learning.bad_case_catcher import BadCaseCatcher, BadCase, FeedbackSource, BadCaseSeverity
from src.learning.case_classifier import CaseClassifier, CaseCategory
from src.learning.feedback_loop import FeedbackLoop, Rule
from src.learning.rule_extractor import RuleExtractor


class TestBadCaseCatcher:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.catcher = BadCaseCatcher()
        self.catcher.cold = __import__('src.memory.cold_memory', fromlist=['ColdMemory']).ColdMemory(storage_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_capture_from_feedback(self):
        case = self.catcher.capture_from_feedback(
            user_input="你好",
            system_output="我不明白",
            feedback="回答太生硬",
        )
        assert case.source == FeedbackSource.USER_REPORT
        assert len(self.catcher.get_unresolved()) == 1

    def test_capture_from_monitor(self):
        case = self.catcher.capture_from_monitor(
            user_input="计算1+1",
            system_output="3",
            error_info="计算错误",
        )
        assert case.source == FeedbackSource.SYSTEM_MONITOR
        assert case.severity == BadCaseSeverity.HIGH

    def test_capture_from_behavior(self):
        case = self.catcher.capture_from_behavior(
            user_input="test",
            system_output="test",
            user_behavior="用户连续追问3次",
        )
        assert case.source == FeedbackSource.BEHAVIOR_CAPTURE

    def test_resolve(self):
        case = self.catcher.capture_from_feedback("input", "output", "error")
        result = self.catcher.resolve(case.id, "已修复")
        assert result is True
        assert case.resolved is True

    def test_get_stats(self):
        self.catcher.capture_from_feedback("a", "b", "error1")
        self.catcher.capture_from_monitor("c", "d", "error2")
        stats = self.catcher.get_stats()
        assert stats["total"] == 2
        assert stats["unresolved"] == 2


class TestCaseClassifier:
    def setup_method(self):
        self.classifier = CaseClassifier()

    @pytest.mark.asyncio
    async def test_classify(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"category": "factual_error", "confidence": 0.9, "subcategory": "知识错误", "reasoning": "事实错误", "suggested_fix": "修正事实"}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.classifier, "_build_llm", return_value=mock_llm):
            result = await self.classifier.classify("case_1", "北京是中国首都", "北京是日本首都")
            assert result.category == CaseCategory.FACTUAL_ERROR
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_classify_parse_failure(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not json"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.classifier, "_build_llm", return_value=mock_llm):
            result = await self.classifier.classify("case_2", "input", "output")
            assert result.category == CaseCategory.OTHER


class TestFeedbackLoop:
    def setup_method(self):
        self.loop = FeedbackLoop()

    @pytest.mark.asyncio
    async def test_process_feedback(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"rules": [{"description": "回答要准确", "category": "accuracy", "trigger": "错误", "action": "验证", "priority": 8}]}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.loop, "_build_llm", return_value=mock_llm):
            result = await self.loop.process_feedback("回答有错误")
            assert len(result.extracted_rules) == 1

    def test_get_active_rules(self):
        self.loop._rules.append(Rule(description="test", active=True))
        self.loop._rules.append(Rule(description="test2", active=False))
        assert len(self.loop.get_active_rules()) == 1

    def test_deactivate_rule(self):
        rule = Rule(description="test")
        self.loop._rules.append(rule)
        result = self.loop.deactivate_rule(rule.id)
        assert result is True
        assert rule.active is False


class TestRuleExtractor:
    def setup_method(self):
        self.extractor = RuleExtractor()

    @pytest.mark.asyncio
    async def test_extract_from_history(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"rules": [{"description": "规则1", "category": "test", "trigger": "条件", "action": "动作", "priority": 5, "confidence": 0.8, "test_cases": ["测试1"]}]}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.extractor, "_build_llm", return_value=mock_llm):
            cases = [{"user_input": "input", "system_output": "output", "error_description": "error", "category": "test"}]
            result = await self.extractor.extract_from_history(cases)
            assert len(result.rules) == 1
            assert result.rules[0].validated is True

    def test_get_golden_rules(self):
        from src.learning.feedback_loop import Rule
        golden = __import__('src.learning.rule_extractor', fromlist=['GoldenRule']).GoldenRule(
            rule=Rule(description="test"),
            validated=True,
        )
        self.extractor._golden_rules.append(golden)
        assert len(self.extractor.get_golden_rules()) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
