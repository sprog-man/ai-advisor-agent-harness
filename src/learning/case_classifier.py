"""Bad Case分类模块 — 事实错误、行为模式、风格偏好"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class CaseCategory(Enum):
    FACTUAL_ERROR = "factual_error"       # 事实错误
    LOGIC_ERROR = "logic_error"           # 逻辑错误
    BEHAVIOR_PATTERN = "behavior_pattern" # 行为模式问题
    STYLE_PREFERENCE = "style_preference" # 风格偏好
    INCOMPLETE = "incomplete"             # 回答不完整
    IRRELEVANT = "irrelevant"             # 回答不相关
    HALLUCINATION = "hallucination"       # 幻觉/编造
    OTHER = "other"


@dataclass
class ClassificationResult:
    case_id: str
    category: CaseCategory
    confidence: float
    subcategory: str = ""
    reasoning: str = ""
    suggested_fix: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class CaseClassifier:
    """Bad Case分类器"""

    def __init__(self):
        self.config = get_config()

    async def classify(
        self,
        case_id: str,
        user_input: str,
        system_output: str,
        expected_output: str = "",
        error_description: str = "",
    ) -> ClassificationResult:
        """分类Bad Case"""
        logger.info("分类Bad Case: %s", case_id)

        llm = self._build_llm()
        prompt = self._build_classify_prompt(user_input, system_output, expected_output, error_description)
        response = await llm.ainvoke(prompt)
        result = self._parse_result(case_id, response)

        logger.info("分类结果: category=%s, confidence=%.2f", result.category.value, result.confidence)
        return result

    async def batch_classify(self, cases: list[dict]) -> list[ClassificationResult]:
        """批量分类"""
        results = []
        for case in cases:
            result = await self.classify(
                case_id=case.get("id", ""),
                user_input=case.get("user_input", ""),
                system_output=case.get("system_output", ""),
                expected_output=case.get("expected_output", ""),
                error_description=case.get("error_description", ""),
            )
            results.append(result)
        return results

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

    def _build_classify_prompt(
        self,
        user_input: str,
        system_output: str,
        expected_output: str,
        error_description: str,
    ) -> str:
        expected_section = f"\n期望输出:\n{expected_output}" if expected_output else ""
        error_section = f"\n错误描述:\n{error_description}" if error_description else ""
        return f"""你是一个Bad Case分类助手。分析以下对话，判断问题类型。

用户输入:
{user_input}

系统输出:
{system_output}
{expected_section}
{error_section}

请返回JSON格式:
{{
    "category": "factual_error|logic_error|behavior_pattern|style_preference|incomplete|irrelevant|hallucination|other",
    "confidence": 0.0-1.0,
    "subcategory": "更具体的分类",
    "reasoning": "分类理由",
    "suggested_fix": "修复建议"
}}

分类说明:
- factual_error: 事实性错误
- logic_error: 逻辑错误
- behavior_pattern: 行为模式问题（如重复、回避等）
- style_preference: 风格偏好（如太正式、太口语化）
- incomplete: 回答不完整
- irrelevant: 回答不相关
- hallucination: 编造不存在的信息
- other: 其他问题

只返回JSON，不要其他内容。"""

    def _parse_result(self, case_id: str, response) -> ClassificationResult:
        import json
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            return ClassificationResult(
                case_id=case_id,
                category=CaseCategory(data.get("category", "other")),
                confidence=float(data.get("confidence", 0.5)),
                subcategory=data.get("subcategory", ""),
                reasoning=data.get("reasoning", ""),
                suggested_fix=data.get("suggested_fix", ""),
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("分类JSON解析失败: %s", e)
            return ClassificationResult(
                case_id=case_id,
                category=CaseCategory.OTHER,
                confidence=0.3,
                reasoning=f"解析失败: {e}",
            )
