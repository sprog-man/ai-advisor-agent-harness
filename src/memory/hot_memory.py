"""热记忆模块 — 当前对话上下文的快速存取"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from collections import deque

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class Message:
    role: str  # "user" | "assistant" | "system"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationContext:
    messages: list[Message] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    summary: str = ""


class HotMemory:
    """热记忆：存储当前对话上下文，支持快速读写"""

    def __init__(self, max_messages: int = 50, max_tokens: int = 4000):
        self.max_messages = max_messages
        self.max_tokens = max_tokens
        self._conversations: dict[str, ConversationContext] = {}
        self._message_buffer: deque[Message] = deque(maxlen=max_messages)

    def get_context(self, session_id: str = "default") -> ConversationContext:
        """获取当前会话上下文"""
        if session_id not in self._conversations:
            self._conversations[session_id] = ConversationContext()
        return self._conversations[session_id]

    def add_message(
        self, role: str, content: str, session_id: str = "default", **metadata
    ) -> Message:
        """添加消息到热记忆"""
        msg = Message(role=role, content=content, metadata=metadata)
        ctx = self.get_context(session_id)
        ctx.messages.append(msg)
        self._message_buffer.append(msg)

        if len(ctx.messages) > self.max_messages:
            overflow = ctx.messages[: len(ctx.messages) - self.max_messages]
            ctx.messages = ctx.messages[len(ctx.messages) - self.max_messages :]
            logger.debug("热记忆溢出 %d 条旧消息", len(overflow))

        logger.debug("热记忆添加消息: role=%s, len=%d", role, len(content))
        return msg

    def get_recent(self, n: int = 10, session_id: str = "default") -> list[Message]:
        """获取最近n条消息"""
        ctx = self.get_context(session_id)
        return ctx.messages[-n:]

    def get_full_context(self, session_id: str = "default") -> list[dict]:
        """获取完整上下文（用于LLM输入）"""
        ctx = self.get_context(session_id)
        return [{"role": m.role, "content": m.content} for m in ctx.messages]

    def update_summary(self, summary: str, session_id: str = "default"):
        """更新会话摘要"""
        ctx = self.get_context(session_id)
        ctx.summary = summary
        logger.debug("热记忆更新摘要: %s", summary[:50])

    def clear(self, session_id: str = "default"):
        """清空会话"""
        if session_id in self._conversations:
            del self._conversations[session_id]
        logger.info("热记忆清空会话: %s", session_id)

    def message_count(self, session_id: str = "default") -> int:
        """获取消息数量"""
        return len(self.get_context(session_id).messages)

    def estimate_tokens(self, session_id: str = "default") -> int:
        """估算token数（粗略：1个中文字≈2token）"""
        ctx = self.get_context(session_id)
        return sum(len(m.content) * 2 for m in ctx.messages)
