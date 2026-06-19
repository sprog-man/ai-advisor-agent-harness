"""任务拆解模块 — 将复杂意图拆解为可执行的子任务"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.core.intent_parser import ParsedIntent, IntentType
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class TaskPriority(Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class SubTask:
    id: str
    description: str
    priority: TaskPriority
    dependencies: list[str] = field(default_factory=list)
    tools_needed: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskPlan:
    original_intent: ParsedIntent
    sub_tasks: list[SubTask]
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class TaskDecomposer:
    """将用户意图拆解为可执行的子任务列表"""

    def __init__(self):
        self.config = get_config()

    async def decompose(self, intent: ParsedIntent) -> TaskPlan:
        """根据意图拆解任务"""
        logger.info("开始拆解任务, 意图类型: %s", intent.intent_type.value)

        if intent.intent_type in (IntentType.CHITCHAT, IntentType.UNKNOWN):
            return TaskPlan(
                original_intent=intent,
                sub_tasks=[
                    SubTask(
                        id="task_direct_reply",
                        description="直接回复用户",
                        priority=TaskPriority.MEDIUM,
                    )
                ],
                reasoning="简单对话，无需复杂拆解",
            )

        llm = self._build_llm()
        prompt = self._build_decompose_prompt(intent)
        response = await llm.ainvoke(prompt)
        plan = self._parse_plan(intent, response)

        logger.info("任务拆解完成: %d 个子任务", len(plan.sub_tasks))
        return plan

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

    def _build_decompose_prompt(self, intent: ParsedIntent) -> str:
        return f"""你是一个任务拆解助手。将用户意图拆解为可执行的子任务。

用户原始输入: {intent.raw_input}
意图类型: {intent.intent_type.value}
关键词: {intent.keywords}

请将任务拆解为2-5个子任务，返回JSON格式:
{{
    "reasoning": "拆解决策理由",
    "sub_tasks": [
        {{
            "id": "task_1",
            "description": "任务描述",
            "priority": "high|medium|low",
            "dependencies": [],
            "tools_needed": ["search", "calculate", "code_execute"]
        }}
    ]
}}

可用工具: search(搜索), calculate(计算), code_execute(代码执行), 
           memory_store(存储记忆), memory_retrieve(检索记忆)

只返回JSON，不要其他内容。"""

    def _parse_plan(self, intent: ParsedIntent, response: str) -> TaskPlan:
        import json
        try:
            text = response.content if hasattr(response, "content") else str(response)
            data = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
            sub_tasks = []
            for t in data.get("sub_tasks", []):
                sub_tasks.append(SubTask(
                    id=t["id"],
                    description=t["description"],
                    priority=TaskPriority(t.get("priority", "medium")),
                    dependencies=t.get("dependencies", []),
                    tools_needed=t.get("tools_needed", []),
                ))
            return TaskPlan(
                original_intent=intent,
                sub_tasks=sub_tasks,
                reasoning=data.get("reasoning", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("任务拆解JSON解析失败: %s", e)
            return TaskPlan(
                original_intent=intent,
                sub_tasks=[
                    SubTask(
                        id="task_fallback",
                        description=intent.raw_input,
                        priority=TaskPriority.MEDIUM,
                    )
                ],
                reasoning=f"拆解失败，回退为单任务: {e}",
            )
