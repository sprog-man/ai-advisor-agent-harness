"""用户意图解析模块 — 将用户输入解析为结构化意图"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class IntentType(Enum):
    QUESTION = "question"
    TASK = "task"
    KNOWLEDGE_QUERY = "knowledge_query"
    CHITCHAT = "chitchat"
    UNKNOWN = "unknown"


@dataclass
class ParsedIntent:
    intent_type: IntentType
    confidence: float
    raw_input: str
    keywords: list[str] = field(default_factory=list)
    entities: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class IntentParser:
    """解析用户输入，提取意图类型和关键信息"""

    def __init__(self):
        self.config = get_config()

    async def parse(self, user_input: str) -> ParsedIntent:
        """解析用户输入为结构化意图"""
        logger.info("解析用户意图: %s", user_input[:50])

        llm = self._build_llm()
        prompt = self._build_parse_prompt(user_input)
        response = await llm.ainvoke(prompt)
        intent = self._parse_response(user_input, response)

        logger.info("意图解析结果: type=%s, confidence=%.2f", intent.intent_type.value, intent.confidence)
        return intent

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

    def _build_parse_prompt(self, user_input: str) -> str:
        return f"""你是一个意图解析助手。分析用户输入并返回JSON格式的意图信息。

用户输入: {user_input}

请返回以下JSON格式:
{{
    "intent_type": "question|task|knowledge_query|chitchat|unknown",
    "confidence": 0.0-1.0,
    "keywords": ["关键词1", "关键词2"],
    "entities": {{}},
    "reasoning": "简短解释为什么判定为此意图"
}}

只返回JSON，不要其他内容。"""

    def _parse_response(self, user_input: str, response: str) -> ParsedIntent:
        import json
        try:
            text = response.content if hasattr(response, "content") else str(response)
            data = json.loads(text.strip().removeprefix("```json").removesuffix("```").strip())
            return ParsedIntent(
                intent_type=IntentType(data.get("intent_type", "unknown")),
                confidence=float(data.get("confidence", 0.5)),
                raw_input=user_input,
                keywords=data.get("keywords", []),
                entities=data.get("entities", {}),
                metadata={"reasoning": data.get("reasoning", "")},
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("意图解析JSON解析失败，使用默认值: %s", e)
            return ParsedIntent(
                intent_type=IntentType.UNKNOWN,
                confidence=0.3,
                raw_input=user_input,
            )
