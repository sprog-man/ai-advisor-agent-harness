"""基础功能链路测试"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.utils.config import AppConfig, LLMConfig
from src.utils.validators import validate_user_input, validate_task_list
from src.core.intent_parser import IntentParser, IntentType, ParsedIntent
from src.core.task_decomposer import TaskDecomposer, TaskPriority
from src.core.tool_executor import ToolExecutor, ToolRegistry, ToolResult
from src.core.summarizer import Summarizer


class TestValidators:
    def test_validate_user_input_valid(self):
        assert validate_user_input("hello") == "hello"

    def test_validate_user_input_strips_whitespace(self):
        assert validate_user_input("  hello  ") == "hello"

    def test_validate_user_input_empty(self):
        with pytest.raises(ValueError):
            validate_user_input("")

    def test_validate_user_input_too_long(self):
        with pytest.raises(ValueError):
            validate_user_input("x" * 10001)

    def test_validate_user_input_not_string(self):
        with pytest.raises(TypeError):
            validate_user_input(123)

    def test_validate_task_list_valid(self):
        tasks = [{"description": "test"}]
        assert validate_task_list(tasks) == tasks

    def test_validate_task_list_not_list(self):
        with pytest.raises(TypeError):
            validate_task_list("not a list")

    def test_validate_task_list_missing_description(self):
        with pytest.raises(KeyError):
            validate_task_list([{"id": 1}])


class TestToolRegistry:
    def test_register_and_get(self):
        reg = ToolRegistry()
        reg.register("custom", lambda x: x)
        assert reg.get("custom") is not None

    def test_get_unknown(self):
        reg = ToolRegistry()
        assert reg.get("nonexistent") is None

    def test_list_tools(self):
        reg = ToolRegistry()
        tools = reg.list_tools()
        assert "search" in tools
        assert "calculate" in tools
        assert "code_execute" in tools


class TestToolExecutor:
    @pytest.mark.asyncio
    async def test_execute_unknown_tool(self):
        executor = ToolExecutor()
        result = await executor.execute("nonexistent")
        assert result.success is False
        assert "未知工具" in result.error

    @pytest.mark.asyncio
    async def test_execute_calculate(self):
        executor = ToolExecutor()
        result = await executor.execute("calculate", expression="1+1")
        assert result.success is True
        assert "2" in str(result.output)

    @pytest.mark.asyncio
    async def test_execute_search(self):
        executor = ToolExecutor()
        result = await executor.execute("search", query="test")
        assert result.success is True

    @pytest.mark.asyncio
    async def test_execute_batch(self):
        executor = ToolExecutor()
        calls = [
            {"tool": "calculate", "kwargs": {"expression": "2+2"}},
            {"tool": "search", "kwargs": {"query": "test"}},
        ]
        results = await executor.execute_batch(calls)
        assert len(results) == 2
        assert all(r.success for r in results)


class TestIntentParser:
    @pytest.mark.asyncio
    async def test_parse_returns_intent(self):
        parser = IntentParser()
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"intent_type": "question", "confidence": 0.9, "keywords": ["test"], "entities": {}, "reasoning": "test"}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(parser, "_build_llm", return_value=mock_llm):
            result = await parser.parse("这是一个测试问题")
            assert isinstance(result, ParsedIntent)
            assert result.intent_type == IntentType.QUESTION
            assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_parse_json_failure_returns_unknown(self):
        parser = IntentParser()
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not json"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(parser, "_build_llm", return_value=mock_llm):
            result = await parser.parse("test")
            assert result.intent_type == IntentType.UNKNOWN


class TestSummarizer:
    @pytest.mark.asyncio
    async def test_summarize(self):
        summarizer = Summarizer()
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "这是一个测试回答"
        mock_llm.ainvoke.return_value = mock_response

        intent = ParsedIntent(
            intent_type=IntentType.QUESTION,
            confidence=0.9,
            raw_input="test",
        )
        results = [ToolResult(tool_name="test", success=True, output="ok")]

        with patch.object(summarizer, "_build_llm", return_value=mock_llm):
            summary = await summarizer.summarize(intent, [], results)
            assert summary.content == "这是一个测试回答"
            assert "test" in summary.sources
