"""全局回退与人工介入模块"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FallbackTrigger(Enum):
    MAX_RETRIES = "max_retries"
    CRITICAL_CONFLICT = "critical_conflict"
    LOW_CONFIDENCE = "low_confidence"
    SYSTEM_ERROR = "system_error"
    USER_REQUEST = "user_request"


@dataclass
class FallbackAction:
    trigger: FallbackTrigger
    action_type: str  # "retry" | "escalate" | "simplify" | "human_intervention"
    description: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FallbackResult:
    triggered: bool
    action: Optional[FallbackAction] = None
    output: str = ""
    needs_human: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class FallbackHandler:
    """全局回退与人工介入处理"""

    def __init__(self):
        self.config = get_config()
        self._human_callback: Optional[Callable] = None
        self._fallback_history: list[FallbackResult] = []

    def set_human_callback(self, callback: Callable):
        """设置人工介入回调"""
        self._human_callback = callback
        logger.info("已设置人工介入回调")

    async def handle(
        self,
        trigger: FallbackTrigger,
        context: str = "",
        error: Optional[Exception] = None,
    ) -> FallbackResult:
        """处理回退"""
        logger.warning("触发回退: %s", trigger.value)

        action = self._determine_action(trigger, error)
        result = FallbackResult(triggered=True, action=action)

        if action.action_type == "human_intervention":
            result.needs_human = True
            if self._human_callback:
                try:
                    human_response = await self._human_callback(context, error)
                    result.output = human_response
                except Exception as e:
                    result.output = f"人工介入回调失败: {e}"
            else:
                result.output = "需要人工介入，但未设置回调"
        elif action.action_type == "simplify":
            result.output = await self._simplify(context)
        else:
            result.output = context

        self._fallback_history.append(result)
        return result

    def should_fallback(
        self,
        retry_count: int,
        confidence: float = 1.0,
        has_critical_conflict: bool = False,
    ) -> Optional[FallbackTrigger]:
        """判断是否需要回退"""
        if retry_count >= 3:
            return FallbackTrigger.MAX_RETRIES
        if has_critical_conflict:
            return FallbackTrigger.CRITICAL_CONFLICT
        if confidence < 0.3:
            return FallbackTrigger.LOW_CONFIDENCE
        return None

    def get_history(self) -> list[FallbackResult]:
        """获取回退历史"""
        return self._fallback_history

    def _determine_action(self, trigger: FallbackTrigger, error: Optional[Exception] = None) -> FallbackAction:
        """根据触发器决定回退动作"""
        if trigger == FallbackTrigger.MAX_RETRIES:
            return FallbackAction(
                trigger=trigger,
                action_type="simplify",
                description="简化请求并重试",
            )
        elif trigger == FallbackTrigger.CRITICAL_CONFLICT:
            return FallbackAction(
                trigger=trigger,
                action_type="human_intervention",
                description="严重冲突，需要人工决策",
            )
        elif trigger == FallbackTrigger.LOW_CONFIDENCE:
            return FallbackAction(
                trigger=trigger,
                action_type="simplify",
                description="置信度过低，简化输出",
            )
        elif trigger == FallbackTrigger.SYSTEM_ERROR:
            return FallbackAction(
                trigger=trigger,
                action_type="human_intervention",
                description="系统错误，需要人工介入",
            )
        else:
            return FallbackAction(
                trigger=trigger,
                action_type="retry",
                description="重试操作",
            )

    async def _simplify(self, context: str) -> str:
        """简化上下文"""
        llm = self._build_llm()
        prompt = f"""请将以下内容简化为核心要点，保持关键信息:

{context}

输出简洁版本:"""
        response = await llm.ainvoke(prompt)
        return response.content if hasattr(response, "content") else str(response)

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.3,
            max_tokens=500,
        )
