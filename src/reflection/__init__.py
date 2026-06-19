# Reflection modules
from .conflict_detector import ConflictDetector, Conflict, ConflictDetectionResult, ConflictType
from .self_correction import SelfCorrection, CorrectionResult
from .agent_debate import AgentDebate, AgentOpinion, DebateResult, AgentRole
from .fallback_handler import FallbackHandler, FallbackTrigger, FallbackAction, FallbackResult

__all__ = [
    "ConflictDetector",
    "Conflict",
    "ConflictDetectionResult",
    "ConflictType",
    "SelfCorrection",
    "CorrectionResult",
    "AgentDebate",
    "AgentOpinion",
    "DebateResult",
    "AgentRole",
    "FallbackHandler",
    "FallbackTrigger",
    "FallbackAction",
    "FallbackResult",
]
