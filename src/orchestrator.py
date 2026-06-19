"""调度器 — 连接所有核心模块，执行完整的处理流程"""

import time
from dataclasses import dataclass, field
from typing import Any

from src.core.intent_parser import IntentParser, ParsedIntent, IntentType
from src.core.task_decomposer import TaskDecomposer, TaskPlan, SubTask
from src.core.knowledge_retriever import KnowledgeRetriever, RetrievalResult
from src.core.tool_executor import ToolExecutor, ToolResult
from src.core.summarizer import Summarizer, Summary
from src.utils.config import get_config
from src.utils.logger import setup_logger
from src.utils.validators import validate_user_input

logger = setup_logger(__name__)


@dataclass
class PipelineResult:
    user_input: str
    intent: ParsedIntent
    plan: TaskPlan
    knowledge: RetrievalResult
    tool_results: list[ToolResult]
    summary: Summary
    elapsed_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


class Orchestrator:
    """端到端处理流程调度器"""

    def __init__(self):
        self.config = get_config()
        self.intent_parser = IntentParser()
        self.task_decomposer = TaskDecomposer()
        self.knowledge_retriever = KnowledgeRetriever()
        self.tool_executor = ToolExecutor()
        self.summarizer = Summarizer()

    async def run(self, user_input: str) -> PipelineResult:
        """执行完整的处理流程"""
        start = time.monotonic()
        user_input = validate_user_input(user_input)

        # 1. 意图解析
        logger.info("========== 步骤 1/5: 意图解析 ==========")
        intent = await self.intent_parser.parse(user_input)

        # 2. 任务拆解
        logger.info("========== 步骤 2/5: 任务拆解 ==========")
        plan = await self.task_decomposer.decompose(intent)

        # 3. 知识检索
        logger.info("========== 步骤 3/5: 知识检索 ==========")
        query = " ".join(intent.keywords) if intent.keywords else intent.raw_input
        knowledge = await self.knowledge_retriever.retrieve(query)

        # 4. 工具执行
        logger.info("========== 步骤 4/5: 工具执行 ==========")
        tool_results = await self._execute_tasks(plan.sub_tasks, knowledge)

        # 5. 总结生成
        logger.info("========== 步骤 5/5: 总结生成 ==========")
        knowledge_context = "\n".join(c.content for c in knowledge.chunks[:3])
        summary = await self.summarizer.summarize(
            intent, plan.sub_tasks, tool_results, knowledge_context
        )

        elapsed = (time.monotonic() - start) * 1000
        logger.info("处理完成，耗时 %.1fms", elapsed)

        return PipelineResult(
            user_input=user_input,
            intent=intent,
            plan=plan,
            knowledge=knowledge,
            tool_results=tool_results,
            summary=summary,
            elapsed_ms=elapsed,
        )

    async def _execute_tasks(
        self, sub_tasks: list[SubTask], knowledge: RetrievalResult
    ) -> list[ToolResult]:
        """根据子任务计划执行工具"""
        results = []
        for task in sub_tasks:
            if not task.tools_needed:
                continue
            for tool_name in task.tools_needed:
                kwargs = {}
                if tool_name == "search":
                    kwargs = {"query": task.description}
                elif tool_name == "calculate":
                    kwargs = {"expression": task.description}
                elif tool_name == "code_execute":
                    kwargs = {"code": task.description}
                else:
                    kwargs = {"query": task.description}
                
                result = await self.tool_executor.execute(tool_name, **kwargs)
                results.append(result)
        return results
