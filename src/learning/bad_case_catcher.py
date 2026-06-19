"""Bad Case捕获模块 — 用户反馈、系统监控、行为捕捉"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from src.memory.cold_memory import ColdMemory, RawRecord
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class FeedbackSource(Enum):
    USER_REPORT = "user_report"         # 用户主动反馈
    SYSTEM_MONITOR = "system_monitor"   # 系统自动检测
    BEHAVIOR_CAPTURE = "behavior_capture"  # 行为捕捉
    A_B_TEST = "a_b_test"              # A/B测试发现


class BadCaseSeverity(Enum):
    CRITICAL = "critical"  # 严重错误
    HIGH = "high"          # 高优先级
    MEDIUM = "medium"      # 中等
    LOW = "low"            # 低优先级


@dataclass
class BadCase:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: FeedbackSource = FeedbackSource.USER_REPORT
    severity: BadCaseSeverity = BadCaseSeverity.MEDIUM
    user_input: str = ""
    system_output: str = ""
    expected_output: str = ""
    error_description: str = ""
    category: str = ""
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    resolved: bool = False
    resolution: str = ""


class BadCaseCatcher:
    """Bad Case捕获器"""

    def __init__(self):
        self.cold = ColdMemory()
        self._cases: list[BadCase] = []

    def capture_from_feedback(
        self,
        user_input: str,
        system_output: str,
        feedback: str,
        severity: BadCaseSeverity = BadCaseSeverity.MEDIUM,
    ) -> BadCase:
        """从用户反馈捕获Bad Case"""
        case = BadCase(
            source=FeedbackSource.USER_REPORT,
            severity=severity,
            user_input=user_input,
            system_output=system_output,
            error_description=feedback,
        )
        self._store_case(case)
        logger.info("捕获Bad Case: source=user_report, severity=%s", severity.value)
        return case

    def capture_from_monitor(
        self,
        user_input: str,
        system_output: str,
        error_info: str,
    ) -> BadCase:
        """从系统监控捕获Bad Case"""
        case = BadCase(
            source=FeedbackSource.SYSTEM_MONITOR,
            severity=BadCaseSeverity.HIGH,
            user_input=user_input,
            system_output=system_output,
            error_description=error_info,
        )
        self._store_case(case)
        logger.info("捕获Bad Case: source=system_monitor")
        return case

    def capture_from_behavior(
        self,
        user_input: str,
        system_output: str,
        user_behavior: str,
    ) -> BadCase:
        """从用户行为捕捉Bad Case"""
        case = BadCase(
            source=FeedbackSource.BEHAVIOR_CAPTURE,
            severity=BadCaseSeverity.LOW,
            user_input=user_input,
            system_output=system_output,
            error_description=f"用户行为异常: {user_behavior}",
        )
        self._store_case(case)
        logger.info("捕获Bad Case: source=behavior_capture")
        return case

    def capture_direct(
        self,
        user_input: str,
        system_output: str,
        expected_output: str,
        source: FeedbackSource = FeedbackSource.USER_REPORT,
        severity: BadCaseSeverity = BadCaseSeverity.MEDIUM,
    ) -> BadCase:
        """直接捕获已知Bad Case"""
        case = BadCase(
            source=source,
            severity=severity,
            user_input=user_input,
            system_output=system_output,
            expected_output=expected_output,
        )
        self._store_case(case)
        return case

    def get_unresolved(self) -> list[BadCase]:
        """获取未解决的Bad Case"""
        return [c for c in self._cases if not c.resolved]

    def get_by_severity(self, severity: BadCaseSeverity) -> list[BadCase]:
        """按严重度获取Bad Case"""
        return [c for c in self._cases if c.severity == severity]

    def get_by_category(self, category: str) -> list[BadCase]:
        """按分类获取Bad Case"""
        return [c for c in self._cases if c.category == category]

    def resolve(self, case_id: str, resolution: str) -> bool:
        """标记Bad Case为已解决"""
        for case in self._cases:
            if case.id == case_id:
                case.resolved = True
                case.resolution = resolution
                logger.info("Bad Case已解决: %s", case_id)
                return True
        return False

    def get_stats(self) -> dict:
        """获取统计信息"""
        total = len(self._cases)
        unresolved = len([c for c in self._cases if not c.resolved])
        by_source = {}
        for c in self._cases:
            by_source[c.source.value] = by_source.get(c.source.value, 0) + 1
        return {"total": total, "unresolved": unresolved, "by_source": by_source}

    def _store_case(self, case: BadCase):
        """存储Bad Case"""
        self._cases.append(case)
        record = RawRecord(
            record_type="bad_case",
            content={
                "id": case.id,
                "source": case.source.value,
                "severity": case.severity.value,
                "user_input": case.user_input,
                "system_output": case.system_output,
                "expected_output": case.expected_output,
                "error_description": case.error_description,
            },
            metadata=case.metadata,
        )
        self.cold.store(record)
