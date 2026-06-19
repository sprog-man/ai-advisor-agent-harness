"""规则提炼模块 — 从历史案例中提炼金标规则"""

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from src.learning.feedback_loop import Rule
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class GoldenRule:
    id: str = ""
    rule: Rule = None
    test_cases: list[dict] = field(default_factory=list)
    pass_rate: float = 0.0
    validated: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    rules: list[GoldenRule]
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class RuleExtractor:
    """从历史案例中提炼金标规则"""

    def __init__(self):
        self.config = get_config()
        self._golden_rules: list[GoldenRule] = []

    async def extract_from_history(
        self, cases: list[dict], min_confidence: float = 0.7
    ) -> ExtractionResult:
        """从历史案例提炼规则"""
        logger.info("从%d个历史案例提炼规则", len(cases))

        llm = self._build_llm()
        prompt = self._build_extraction_prompt(cases)
        response = await llm.ainvoke(prompt)
        rules = self._parse_extraction(response)

        validated_rules = []
        for gr in rules:
            if gr.rule.confidence >= min_confidence:
                gr.validated = True
                validated_rules.append(gr)
                self._golden_rules.append(gr)

        logger.info("提炼了%d条规则，%d条通过验证", len(rules), len(validated_rules))
        return ExtractionResult(
            rules=validated_rules,
            summary=f"从{len(cases)}个案例中提炼了{len(validated_rules)}条金标规则",
        )

    async def validate_rule(self, rule: Rule, test_cases: list[dict]) -> GoldenRule:
        """验证规则"""
        logger.info("验证规则: %s", rule.description)

        llm = self._build_llm()
        prompt = self._build_validation_prompt(rule, test_cases)
        response = await llm.ainvoke(prompt)
        result = self._parse_validation(response, rule)

        return result

    def get_golden_rules(self) -> list[GoldenRule]:
        """获取所有金标规则"""
        return [r for r in self._golden_rules if r.validated]

    def get_rules_by_category(self, category: str) -> list[GoldenRule]:
        """按分类获取金标规则"""
        return [r for r in self._golden_rules if r.rule.category == category and r.validated]

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.2,
            max_tokens=1500,
        )

    def _build_extraction_prompt(self, cases: list[dict]) -> str:
        cases_text = "\n".join(
            f"案例{i+1}:\n  输入: {c.get('user_input', '')}\n  输出: {c.get('system_output', '')}\n  问题: {c.get('error_description', '')}\n  分类: {c.get('category', '')}"
            for i, c in enumerate(cases[:10])
        )
        return f"""分析以下历史Bad Case，提炼可复用的规则。

历史案例:
{cases_text}

请返回JSON格式的规则列表:
{{
    "rules": [
        {{
            "description": "规则描述",
            "category": "分类",
            "trigger": "触发条件",
            "action": "应执行的动作",
            "priority": 1-10,
            "confidence": 0.0-1.0,
            "test_cases": ["测试用例1", "测试用例2"]
        }}
    ]
}}

规则要求:
1. 具有通用性，能适用于类似场景
2. 明确触发条件和执行动作
3. 基于实际案例，非假设

只返回JSON，不要其他内容。"""

    def _build_validation_prompt(self, rule: Rule, test_cases: list[dict]) -> str:
        cases_text = "\n".join(
            f"- {c.get('input', '')}" for c in test_cases
        )
        return f"""验证以下规则是否有效。

规则: {rule.description}
触发条件: {rule.trigger}
执行动作: {rule.action}

测试用例:
{cases_text}

请返回JSON格式:
{{
    "pass_count": 通过的用例数,
    "total_count": 总用例数,
    "pass_rate": 0.0-1.0,
    "issues": ["发现的问题"],
    "suggestions": ["改进建议"]
}}

只返回JSON，不要其他内容。"""

    def _parse_extraction(self, response) -> list[GoldenRule]:
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            rules = []
            for r in data.get("rules", []):
                rule = Rule(
                    description=r.get("description", ""),
                    category=r.get("category", ""),
                    trigger=r.get("trigger", ""),
                    action=r.get("action", ""),
                    priority=r.get("priority", 5),
                    confidence=r.get("confidence", 0.7),
                )
                golden = GoldenRule(rule=rule, test_cases=r.get("test_cases", []))
                rules.append(golden)
            return rules
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("规则提取JSON解析失败: %s", e)
            return []

    def _parse_validation(self, response, rule: Rule) -> GoldenRule:
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            pass_rate = data.get("pass_rate", 0.0)
            return GoldenRule(
                rule=rule,
                pass_rate=pass_rate,
                validated=pass_rate >= 0.7,
                metadata={
                    "pass_count": data.get("pass_count", 0),
                    "total_count": data.get("total_count", 0),
                    "issues": data.get("issues", []),
                    "suggestions": data.get("suggestions", []),
                },
            )
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("验证JSON解析失败: %s", e)
            return GoldenRule(rule=rule, pass_rate=0.0, validated=False)
