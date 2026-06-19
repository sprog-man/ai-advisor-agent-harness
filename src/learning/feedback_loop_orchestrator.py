"""反馈循环编排器 — 协调反馈→反思→规则→遵循的完整闭环"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Optional

from src.memory.memory_manager import MemoryManager
from src.reflection.conflict_detector import ConflictDetector, ConflictDetectionResult
from src.reflection.self_correction import SelfCorrection
from src.learning.feedback_loop import FeedbackLoop, Rule
from src.learning.rule_extractor import RuleExtractor, GoldenRule
from src.learning.bad_case_catcher import BadCaseCatcher, BadCase
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class FeedbackEntry:
    content: str
    source: str = "user"
    context: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvolutionResult:
    feedback: str
    rules_extracted: int
    rules_applied: int
    conflicts_detected: int
    corrections_made: int
    golden_rules_updated: int
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemState:
    total_feedbacks: int = 0
    total_rules: int = 0
    total_golden_rules: int = 0
    total_corrections: int = 0
    active_rules: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class FeedbackLoopOrchestrator:
    """反馈循环编排器：接收反馈→反思→提炼规则→后续遵循"""

    def __init__(self):
        self.config = get_config()
        self.memory = MemoryManager()
        self.bad_case_catcher = BadCaseCatcher()
        self.conflict_detector = ConflictDetector()
        self.self_correction = SelfCorrection()
        self.feedback_loop = FeedbackLoop()
        self.rule_extractor = RuleExtractor()
        self._feedback_history: list[FeedbackEntry] = []
        self._applied_rules: list[Rule] = []

    async def process_feedback(self, feedback: str, context: Optional[str] = None) -> EvolutionResult:
        """处理反馈，执行完整闭环"""
        logger.info("处理反馈: %s", feedback[:50])

        entry = FeedbackEntry(content=feedback, context=context)
        self._feedback_history.append(entry)

        await self.memory.record_conversation("feedback", feedback, "feedback_loop")

        rules_extracted = 0
        rules_applied = 0
        conflicts_detected = 0
        corrections_made = 0

        conflict_result = await self.conflict_detector.detect(feedback, context)
        if conflict_result.has_conflict:
            conflicts_detected = len(conflict_result.conflicts)
            correction_result = await self.self_correction.correct(feedback, conflict_result)
            if correction_result.success:
                corrections_made = 1
                feedback = correction_result.corrected

        loop_result = await self.feedback_loop.process_feedback(feedback, context)
        rules_extracted = len(loop_result.extracted_rules)
        rules_applied = len(loop_result.applied_rules)
        self._applied_rules.extend(loop_result.extracted_rules)

        golden_rules = []
        if rules_extracted > 0:
            cases = [{"user_input": feedback, "system_output": "", "error_description": feedback, "category": "feedback"}]
            extraction_result = await self.rule_extractor.extract_from_history(cases)
            golden_rules = extraction_result.rules

        summary = f"提取{rules_extracted}条规则，应用{rules_applied}条，检测{conflicts_detected}个冲突，修正{corrections_made}次"

        await self.memory.extract_and_store(
            f"反馈处理: {summary}",
            entry_type="event",
        )

        return EvolutionResult(
            feedback=feedback,
            rules_extracted=rules_extracted,
            rules_applied=rules_applied,
            conflicts_detected=conflicts_detected,
            corrections_made=corrections_made,
            golden_rules_updated=len(golden_rules),
            summary=summary,
        )

    async def apply_rules_to_context(self, context: str) -> str:
        """将规则应用到上下文"""
        active_rules = self.feedback_loop.get_active_rules()
        if not active_rules:
            return context

        applicable = [r for r in active_rules if r.trigger.lower() in context.lower()]
        if not applicable:
            return context

        rules_text = "\n".join(f"- {r.description} (触发: {r.trigger}, 动作: {r.action})" for r in applicable[:5])
        enhanced_context = f"{context}\n\n遵循规则:\n{rules_text}"
        return enhanced_context

    async def learn_from_cases(self, cases: list[dict]) -> int:
        """从Bad Case中学习"""
        logger.info("从%d个Bad Case学习", len(cases))

        for case in cases:
            self.bad_case_catcher.capture_direct(
                user_input=case.get("user_input", ""),
                system_output=case.get("system_output", ""),
                expected_output=case.get("expected_output", ""),
            )

        if cases:
            extraction_result = await self.rule_extractor.extract_from_history(cases)
            for golden_rule in extraction_result.rules:
                if golden_rule.validated:
                    self.feedback_loop._rules.append(golden_rule.rule)

            return len(extraction_result.rules)
        return 0

    def get_state(self) -> SystemState:
        """获取系统状态"""
        return SystemState(
            total_feedbacks=len(self._feedback_history),
            total_rules=len(self.feedback_loop._rules),
            total_golden_rules=len(self.rule_extractor.get_golden_rules()),
            active_rules=len(self.feedback_loop.get_active_rules()),
        )

    def get_feedback_history(self) -> list[FeedbackEntry]:
        """获取反馈历史"""
        return self._feedback_history

    def get_applied_rules(self) -> list[Rule]:
        """获取已应用的规则"""
        return self._applied_rules

    async def get_system_prompt(self) -> str:
        """生成包含学习规则的系统提示"""
        golden_rules = self.rule_extractor.get_golden_rules()
        if not golden_rules:
            return ""

        rules_text = "\n".join(
            f"- {gr.rule.description} (触发: {gr.rule.trigger}, 动作: {gr.rule.action})"
            for gr in golden_rules[:10]
        )
        return f"遵循以下学习到的规则:\n{rules_text}"
