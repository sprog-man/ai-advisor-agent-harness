"""知识检索模块 — 从向量知识库检索相关知识"""

import os
from dataclasses import dataclass, field
from typing import Any, Optional

from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class KnowledgeChunk:
    content: str
    source: str = ""
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    query: str
    chunks: list[KnowledgeChunk]
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class KnowledgeRetriever:
    """从向量知识库检索与查询相关的知识"""

    def __init__(self):
        self.config = get_config()
        self._vector_store = None

    async def retrieve(self, query: str, top_k: int = 5) -> RetrievalResult:
        """检索与查询相关的知识"""
        logger.info("检索知识: %s (top_k=%d)", query[:50], top_k)

        store = await self._get_vector_store()
        if store is None:
            logger.warning("向量库未初始化，返回空结果")
            return RetrievalResult(query=query, chunks=[], summary="知识库未就绪")

        docs = store.similarity_search_with_score(query, k=top_k)
        chunks = []
        for doc, score in docs:
            chunks.append(KnowledgeChunk(
                content=doc.page_content,
                source=doc.metadata.get("source", ""),
                score=float(score),
                metadata=doc.metadata,
            ))

        logger.info("检索到 %d 个知识片段", len(chunks))
        return RetrievalResult(query=query, chunks=chunks)

    async def add_document(self, content: str, metadata: Optional[dict] = None) -> bool:
        """添加文档到向量库"""
        logger.info("添加文档到知识库")
        store = await self._get_vector_store()
        if store is None:
            logger.error("向量库未初始化")
            return False

        from langchain_core.documents import Document
        doc = Document(page_content=content, metadata=metadata or {})
        store.add_documents([doc])
        return True

    async def _get_vector_store(self):
        if self._vector_store is not None:
            return self._vector_store

        try:
            from langchain_chroma import Chroma
            from langchain_openai import OpenAIEmbeddings

            cfg = self.config.vector_db
            embedding_model = os.getenv("EMBEDDING_MODEL", "")
            
            if not embedding_model:
                logger.info("未配置embedding模型，跳过向量库初始化")
                return None
                
            embeddings = OpenAIEmbeddings(
                model=embedding_model,
                api_key=self.config.llm.api_key,
                base_url=self.config.llm.base_url,
            )
            self._vector_store = Chroma(
                collection_name=cfg.collection_name,
                embedding_function=embeddings,
                host=cfg.host,
                port=cfg.port,
            )
            logger.info("向量库连接成功: %s:%d", cfg.host, cfg.port)
            return self._vector_store
        except Exception as e:
            logger.warning("向量库初始化失败: %s", e)
            return None
