"""总结生成模块 — 将任务执行结果生成最终回答"""

from dataclasses import dataclass
from typing import Any

from src.core.intent_parser import ParsedIntent
from src.core.task_decomposer import SubTask
from src.core.tool_executor import ToolResult
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Summary:
    content: str
    sources: list[str]
    metadata: dict[str, Any]


class Summarizer:
    """将多步执行结果整合为结构化回答"""

    def __init__(self):
        self.config = get_config()

    async def summarize(
        self,
        intent: ParsedIntent,
        sub_tasks: list[SubTask],
        tool_results: list[ToolResult],
        knowledge_context: str = "",
    ) -> Summary:
        """生成最终总结"""
        logger.info("生成总结，基于 %d 个工具结果", len(tool_results))

        llm = self._build_llm()
        prompt = self._build_summary_prompt(intent, sub_tasks, tool_results, knowledge_context)
        response = await llm.ainvoke(prompt)

        content = response.content if hasattr(response, "content") else str(response)
        sources = [r.tool_name for r in tool_results if r.success]

        return Summary(
            content=content.strip(),
            sources=sources,
            metadata={"tool_count": len(tool_results), "success_count": len(sources)},
        )

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            max_tokens=cfg.max_tokens,
        )

    def _build_summary_prompt(
        self,
        intent: ParsedIntent,
        sub_tasks: list[SubTask],
        tool_results: list[ToolResult],
        knowledge_context: str,
    ) -> str:
        results_text = "\n".join(
            f"- 工具: {r.tool_name}, 结果: {r.output}" if r.success
            else f"- 工具: {r.tool_name}, 失败: {r.error}"
            for r in tool_results
        )

        tasks_text = "\n".join(
            f"- [{t.priority.value}] {t.description}" for t in sub_tasks
        )

        knowledge_section = f"\n相关知识:\n{knowledge_context}" if knowledge_context else ""

        return f"""你是一个AI顾问助手。请根据以下信息生成一个清晰、结构化的回答。

用户意图: {intent.raw_input}
意图类型: {intent.intent_type.value}

任务执行结果:
{tasks_text}

工具调用结果:
{results_text}
{knowledge_section}

请生成一个完整、有条理的回答，包含:
1. 对用户问题的直接回答
2. 从工具执行结果中提取的关键信息
3. 如果有相关知识，整合进来

回答要求：准确、简洁、有条理。"""
