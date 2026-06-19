"""冲突检测模块 — 检测逻辑矛盾和不一致"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class ConflictType(Enum):
    LOGICAL = "logical"           # 逻辑矛盾
    FACTUAL = "factual"           # 事实冲突
    CONSISTENCY = "consistency"   # 一致性问题
    COMPLETENESS = "completeness" # 完整性问题
    NONE = "none"


@dataclass
class Conflict:
    conflict_type: ConflictType
    description: str
    severity: str = "medium"  # "low" | "medium" | "high"
    involved_items: list[str] = field(default_factory=list)
    suggestion: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConflictDetectionResult:
    has_conflict: bool
    conflicts: list[Conflict]
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class ConflictDetector:
    """检测输出结果中的逻辑冲突"""

    def __init__(self):
        self.config = get_config()

    async def detect(self, content: str, context: Optional[str] = None) -> ConflictDetectionResult:
        """检测内容中的冲突"""
        logger.info("检测冲突: %s", content[:50])

        llm = self._build_llm()
        prompt = self._build_detection_prompt(content, context)
        response = await llm.ainvoke(prompt)
        result = self._parse_result(response)

        logger.info("冲突检测完成: has_conflict=%s, count=%d", result.has_conflict, len(result.conflicts))
        return result

    async def detect_between(self, text_a: str, text_b: str) -> ConflictDetectionResult:
        """检测两段文本之间的冲突"""
        logger.info("检测文本间冲突")

        llm = self._build_llm()
        prompt = self._build_comparison_prompt(text_a, text_b)
        response = await llm.ainvoke(prompt)
        result = self._parse_result(response)

        return result

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.2,
            max_tokens=1000,
        )

    def _build_detection_prompt(self, content: str, context: Optional[str] = None) -> str:
        context_section = f"\n上下文:\n{context}" if context else ""
        return f"""你是一个冲突检测助手。分析以下内容，检测是否存在逻辑矛盾、事实冲突或不一致。

内容:
{content}
{context_section}

请返回JSON格式:
{{
    "has_conflict": true/false,
    "conflicts": [
        {{
            "type": "logical|factual|consistency|completeness",
            "description": "冲突描述",
            "severity": "low|medium|high",
            "involved_items": ["涉及的内容片段"],
            "suggestion": "修复建议"
        }}
    ],
    "summary": "冲突总结"
}}

如果没有冲突，conflicts为空数组，has_conflict为false。
只返回JSON，不要其他内容。"""

    def _build_comparison_prompt(self, text_a: str, text_b: str) -> str:
        return f"""你是一个冲突检测助手。比较以下两段文本，检测是否存在矛盾。

文本A:
{text_a}

文本B:
{text_b}

请返回JSON格式:
{{
    "has_conflict": true/false,
    "conflicts": [
        {{
            "type": "logical|factual|consistency",
            "description": "冲突描述",
            "severity": "low|medium|high",
            "involved_items": ["文本A中的内容", "文本B中的内容"],
            "suggestion": "修复建议"
        }}
    ],
    "summary": "冲突总结"
}}

只返回JSON，不要其他内容。"""

    def _parse_result(self, response) -> ConflictDetectionResult:
        import json
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            conflicts = []
            for c in data.get("conflicts", []):
                conflicts.append(Conflict(
                    conflict_type=ConflictType(c.get("type", "none")),
                    description=c.get("description", ""),
                    severity=c.get("severity", "medium"),
                    involved_items=c.get("involved_items", []),
                    suggestion=c.get("suggestion", ""),
                ))

            return ConflictDetectionResult(
                has_conflict=data.get("has_conflict", False),
                conflicts=conflicts,
                summary=data.get("summary", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("冲突检测JSON解析失败: %s", e)
            return ConflictDetectionResult(has_conflict=False, conflicts=[], summary=f"检测失败: {e}")
