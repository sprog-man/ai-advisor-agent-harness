"""温记忆模块 — 向量库+知识图谱双模存储"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    entry_type: str = ""  # "fact" | "preference" | "event" | "knowledge"
    source: str = ""
    embedding: Optional[list[float]] = None
    triples: list[dict] = field(default_factory=list)  # 知识图谱三元组
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_accessed: str = field(default_factory=lambda: datetime.now().isoformat())
    access_count: int = 0
    relevance_score: float = 0.0


@dataclass
class Triple:
    """知识图谱三元组：(主语, 谓语, 宾语)"""
    subject: str
    predicate: str
    obj: str
    confidence: float = 1.0
    source: str = ""


class WarmMemory:
    """温记忆：向量库语义搜索 + 知识图谱精确查询"""

    def __init__(self):
        self.config = get_config()
        self._vector_store = None
        self._triples: list[Triple] = []

    async def store(
        self,
        content: str,
        entry_type: str = "knowledge",
        triples: Optional[list[Triple]] = None,
        **metadata,
    ) -> MemoryEntry:
        """存储记忆到温记忆"""
        entry = MemoryEntry(
            content=content,
            entry_type=entry_type,
            triples=[],
            metadata=metadata,
        )

        if triples:
            entry.triples = [{"subject": t.subject, "predicate": t.predicate, "object": t.obj, "confidence": t.confidence, "source": t.source} for t in triples]
            self._triples.extend(triples)

        try:
            store = await self._get_vector_store()
            if store:
                from langchain_core.documents import Document
                doc = Document(
                    page_content=content,
                    metadata={
                        "id": entry.id,
                        "type": entry_type,
                        "source": entry.source,
                        "created_at": entry.created_at,
                        **metadata,
                    },
                )
                store.add_documents([doc])
                logger.info("温记忆存储: type=%s, len=%d", entry_type, len(content))
        except Exception as e:
            logger.warning("向量存储失败，仅存储三元组: %s", e)

        return entry

    async def search(
        self, query: str, top_k: int = 5, entry_type: Optional[str] = None
    ) -> list[MemoryEntry]:
        """语义搜索温记忆"""
        store = await self._get_vector_store()
        if not store:
            logger.warning("向量库未连接，返回空结果")
            return []

        filter_dict = {"type": entry_type} if entry_type else None
        docs = store.similarity_search_with_score(query, k=top_k, filter=filter_dict)

        results = []
        for doc, score in docs:
            entry = MemoryEntry(
                id=doc.metadata.get("id", str(uuid.uuid4())),
                content=doc.page_content,
                entry_type=doc.metadata.get("type", "unknown"),
                source=doc.metadata.get("source", ""),
                relevance_score=float(score),
                metadata=doc.metadata,
            )
            results.append(entry)

        logger.info("温记忆语义搜索: query=%s, 结果数=%d", query[:30], len(results))
        return results

    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        obj: Optional[str] = None,
    ) -> list[Triple]:
        """知识图谱精确查询"""
        results = []
        for t in self._triples:
            if subject and t.subject != subject:
                continue
            if predicate and t.predicate != predicate:
                continue
            if obj and t.obj != obj:
                continue
            results.append(t)

        logger.info("知识图谱查询: 结果数=%d", len(results))
        return results

    def add_triple(self, triple: Triple):
        """直接添加三元组"""
        self._triples.append(triple)
        logger.debug("添加三元组: (%s, %s, %s)", triple.subject, triple.predicate, triple.obj)

    async def get_context(
        self, query: str, max_entries: int = 5
    ) -> str:
        """获取相关上下文（用于LLM增强）"""
        entries = await self.search(query, top_k=max_entries)
        if not entries:
            return ""

        context_parts = []
        for e in entries:
            context_parts.append(f"[{e.entry_type}] {e.content}")

        triples = self.query_triples()
        if triples:
            triple_strs = [f"{t.subject}-{t.predicate}-{t.obj}" for t in triples[:10]]
            context_parts.append(f"知识图谱: {'; '.join(triple_strs)}")

        return "\n".join(context_parts)

    async def _get_vector_store(self):
        if self._vector_store is not None:
            return self._vector_store

        try:
            from langchain_chroma import Chroma

            cfg = self.config.vector_db
            embeddings = self._get_embeddings()

            self._vector_store = Chroma(
                collection_name="warm_memory",
                embedding_function=embeddings,
                host=cfg.host,
                port=cfg.port,
            )
            return self._vector_store
        except Exception as e:
            logger.warning("向量库连接失败: %s", e)
            return None

    def _get_embeddings(self):
        import os
        embedding_model = os.getenv("EMBEDDING_MODEL", "")
        embedding_provider = os.getenv("EMBEDDING_PROVIDER", "openai")
        embedding_api_key = os.getenv("EMBEDDING_API_KEY", "")
        embedding_base_url = os.getenv("EMBEDDING_BASE_URL", "")
        
        if not embedding_model:
            raise ValueError("未配置embedding模型")
        
        if embedding_provider == "dashscope":
            from langchain_community.embeddings import DashScopeEmbeddings
            return DashScopeEmbeddings(
                model=embedding_model,
                dashscope_api_key=embedding_api_key,
            )
        elif embedding_provider == "openai":
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                model=embedding_model,
                api_key=embedding_api_key or self.config.llm.api_key,
                base_url=embedding_base_url or self.config.llm.base_url,
            )
        else:
            from langchain_openai import OpenAIEmbeddings
            return OpenAIEmbeddings(
                model=embedding_model,
                api_key=embedding_api_key or self.config.llm.api_key,
            )
