"""自我修正模块 — 局部重试与修正"""

from dataclasses import dataclass, field
from typing import Any, Optional

from src.reflection.conflict_detector import Conflict, ConflictDetectionResult
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class CorrectionResult:
    original: str
    corrected: str
    changes_made: list[str] = field(default_factory=list)
    success: bool = True
    attempts: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class SelfCorrection:
    """基于冲突检测结果进行自我修正"""

    def __init__(self, max_retries: int = 3):
        self.config = get_config()
        self.max_retries = max_retries

    async def correct(
        self, content: str, conflict_result: ConflictDetectionResult
    ) -> CorrectionResult:
        """根据冲突检测结果修正内容"""
        if not conflict_result.has_conflict:
            return CorrectionResult(original=content, corrected=content, success=True)

        logger.info("开始自我修正，冲突数: %d", len(conflict_result.conflicts))

        corrected = content
        changes = []

        for attempt in range(1, self.max_retries + 1):
            logger.info("修正尝试 %d/%d", attempt, self.max_retries)

            llm = self._build_llm()
            prompt = self._build_correction_prompt(corrected, conflict_result)
            response = await llm.ainvoke(prompt)

            new_content = self._parse_correction(response)
            if new_content and new_content != corrected:
                changes.append(f"尝试{attempt}: 修正了冲突")
                corrected = new_content

                from src.reflection.conflict_detector import ConflictDetector
                detector = ConflictDetector()
                new_conflict = await detector.detect(corrected)

                if not new_conflict.has_conflict:
                    logger.info("修正成功，冲突已解决")
                    return CorrectionResult(
                        original=content,
                        corrected=corrected,
                        changes_made=changes,
                        success=True,
                        attempts=attempt,
                    )

            logger.warning("修正尝试 %d 未完全解决冲突", attempt)

        return CorrectionResult(
            original=content,
            corrected=corrected,
            changes_made=changes,
            success=False,
            attempts=self.max_retries,
        )

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

    def _build_correction_prompt(self, content: str, conflict_result: ConflictDetectionResult) -> str:
        conflicts_text = "\n".join(
            f"- [{c.conflict_type.value}] {c.description} (严重度: {c.severity})\n  建议: {c.suggestion}"
            for c in conflict_result.conflicts
        )
        return f"""你是一个内容修正助手。根据检测到的冲突，修正以下内容。

原始内容:
{content}

检测到的冲突:
{conflicts_text}

请修正内容以解决所有冲突，返回修正后的完整内容。
只返回修正后的内容，不要其他解释。"""

    def _parse_correction(self, response) -> Optional[str]:
        content = response.content if hasattr(response, "content") else str(response)
        content = content.strip()
        if content.startswith("```"):
            content = content.removeprefix("```").removesuffix("```").strip()
        return content if content else None
