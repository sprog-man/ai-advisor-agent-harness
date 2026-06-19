"""记忆管理器 — 协调热-温-冷三层记忆"""

from typing import Any, Optional

from src.memory.hot_memory import HotMemory, Message, ConversationContext
from src.memory.warm_memory import WarmMemory, MemoryEntry, Triple
from src.memory.cold_memory import ColdMemory, RawRecord
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class MemoryManager:
    """三层记忆统一管理器"""

    def __init__(self):
        self.hot = HotMemory()
        self.warm = WarmMemory()
        self.cold = ColdMemory()

    async def record_conversation(
        self, role: str, content: str, session_id: str = "default", **metadata
    ) -> Message:
        """记录对话（热记忆）"""
        msg = self.hot.add_message(role, content, session_id, **metadata)

        record = RawRecord(
            record_type="conversation",
            content={"role": role, "content": content},
            metadata=metadata,
            session_id=session_id,
        )
        self.cold.store(record)

        return msg

    async def extract_and_store(
        self, content: str, entry_type: str = "knowledge", **metadata
    ) -> MemoryEntry:
        """从内容提取关键信息存储到温记忆"""
        entry = await self.warm.store(content, entry_type, **metadata)

        record = RawRecord(
            record_type="knowledge",
            content=content,
            metadata={"entry_type": entry_type, "entry_id": entry.id, **metadata},
        )
        self.cold.store(record)

        return entry

    async def retrieve_context(
        self, query: str, session_id: str = "default", max_entries: int = 5
    ) -> str:
        """检索相关上下文（热+温）"""
        hot_ctx = self.hot.get_context(session_id)
        hot_context = ""
        if hot_ctx.messages:
            recent = self.hot.get_recent(5, session_id)
            hot_context = "\n".join(f"[{m.role}] {m.content}" for m in recent)

        warm_context = await self.warm.get_context(query, max_entries)

        parts = []
        if hot_context:
            parts.append(f"对话上下文:\n{hot_context}")
        if warm_context:
            parts.append(f"相关知识:\n{warm_context}")

        return "\n\n".join(parts)

    async def store_fact(
        self, fact: str, triples: Optional[list[Triple]] = None, **metadata
    ) -> MemoryEntry:
        """存储事实（温记忆）"""
        return await self.warm.store(fact, "fact", triples, **metadata)

    async def store_preference(self, preference: str, **metadata) -> MemoryEntry:
        """存储偏好（温记忆）"""
        return await self.warm.store(preference, "preference", **metadata)

    async def search_memory(self, query: str, top_k: int = 5) -> list[MemoryEntry]:
        """语义搜索温记忆"""
        return await self.warm.search(query, top_k)

    def query_knowledge(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        obj: Optional[str] = None,
    ) -> list[Triple]:
        """查询知识图谱"""
        return self.warm.query_triples(subject, predicate, obj)

    def get_stats(self) -> dict:
        """获取记忆统计"""
        return {
            "hot_messages": self.hot.message_count(),
            "hot_tokens": self.hot.estimate_tokens(),
            "cold_records": self.cold.count(),
            "cold_conversations": self.cold.count("conversation"),
            "cold_knowledge": self.cold.count("knowledge"),
        }

    def clear_session(self, session_id: str = "default"):
        """清空会话热记忆"""
        self.hot.clear(session_id)
        logger.info("清空会话: %s", session_id)
