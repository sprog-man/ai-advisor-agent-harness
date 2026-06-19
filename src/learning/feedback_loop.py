"""反馈循环模块 — 接收反馈→反思→提炼规则→后续遵循"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Rule:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""
    category: str = ""
    trigger: str = ""  # 触发条件
    action: str = ""   # 应执行的动作
    priority: int = 1  # 1-10, 10最高
    source_case_id: str = ""
    confidence: float = 0.8
    active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FeedbackLoopResult:
    feedback: str
    extracted_rules: list[Rule]
    applied_rules: list[Rule]
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class FeedbackLoop:
    """反馈循环：接收反馈→反思→提炼规则→后续遵循"""

    def __init__(self):
        self.config = get_config()
        self._rules: list[Rule] = []

    async def process_feedback(
        self,
        feedback: str,
        context: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> FeedbackLoopResult:
        """处理反馈，提取规则"""
        logger.info("处理反馈: %s", feedback[:50])

        new_rules = await self._extract_rules(feedback, context, case_id)
        self._rules.extend(new_rules)

        applied = self._find_applicable_rules(feedback)

        return FeedbackLoopResult(
            feedback=feedback,
            extracted_rules=new_rules,
            applied_rules=applied,
            summary=f"提取了{len(new_rules)}条规则，应用了{len(applied)}条",
        )

    async def extract_rules_from_cases(self, cases: list[dict]) -> list[Rule]:
        """从多个Bad Case中提取规则"""
        logger.info("从%d个Bad Case提取规则", len(cases))

        cases_text = "\n".join(
            f"- 输入: {c.get('user_input', '')}\n  输出: {c.get('system_output', '')}\n  问题: {c.get('error_description', '')}"
            for c in cases
        )

        llm = self._build_llm()
        prompt = f"""分析以下Bad Case，提取通用规则以避免类似错误。

Bad Cases:
{cases_text}

请返回JSON格式的规则列表:
{{
    "rules": [
        {{
            "description": "规则描述",
            "category": "分类",
            "trigger": "触发条件",
            "action": "应执行的动作",
            "priority": 1-10
        }}
    ]
}}

只返回JSON，不要其他内容。"""
        response = await llm.ainvoke(prompt)
        return self._parse_rules(response, cases[0].get("id", "") if cases else "")

    def get_active_rules(self) -> list[Rule]:
        """获取所有激活的规则"""
        return [r for r in self._rules if r.active]

    def get_rules_by_category(self, category: str) -> list[Rule]:
        """按分类获取规则"""
        return [r for r in self._rules if r.category == category and r.active]

    def deactivate_rule(self, rule_id: str) -> bool:
        """停用规则"""
        for rule in self._rules:
            if rule.id == rule_id:
                rule.active = False
                return True
        return False

    def _find_applicable_rules(self, context: str) -> list[Rule]:
        """查找适用的规则"""
        applicable = []
        for rule in self._rules:
            if rule.active and rule.trigger.lower() in context.lower():
                applicable.append(rule)
        return sorted(applicable, key=lambda r: r.priority, reverse=True)

    async def _extract_rules(self, feedback: str, context: Optional[str], case_id: Optional[str]) -> list[Rule]:
        """从反馈中提取规则"""
        llm = self._build_llm()
        context_section = f"\n上下文:\n{context}" if context else ""
        prompt = f"""从以下反馈中提取可执行的规则。

反馈: {feedback}
{context_section}

请返回JSON格式:
{{
    "rules": [
        {{
            "description": "规则描述",
            "category": "分类",
            "trigger": "触发条件",
            "action": "应执行的动作",
            "priority": 1-10
        }}
    ]
}}

只返回JSON，不要其他内容。"""
        response = await llm.ainvoke(prompt)
        return self._parse_rules(response, case_id or "")

    def _parse_rules(self, response, case_id: str) -> list[Rule]:
        import json
        try:
            text = response.content if hasattr(response, "content") else str(response)
            text = text.strip().removeprefix("```json").removesuffix("```").strip()
            data = json.loads(text)

            rules = []
            for r in data.get("rules", []):
                rules.append(Rule(
                    description=r.get("description", ""),
                    category=r.get("category", ""),
                    trigger=r.get("trigger", ""),
                    action=r.get("action", ""),
                    priority=r.get("priority", 5),
                    source_case_id=case_id,
                ))
            return rules
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.warning("规则提取JSON解析失败: %s", e)
            return []

    def _build_llm(self):
        from langchain_openai import ChatOpenAI
        cfg = self.config.llm
        return ChatOpenAI(
            model=cfg.model,
            api_key=cfg.api_key,
            base_url=cfg.base_url,
            temperature=0.3,
            max_tokens=1500,
        )
