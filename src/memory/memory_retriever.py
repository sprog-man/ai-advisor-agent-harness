"""记忆检索模块 — 向量库语义搜索+知识图谱精确查询，结果融合"""

from dataclasses import dataclass, field
from typing import Any, Optional

from src.memory.warm_memory import WarmMemory, MemoryEntry, Triple
from src.memory.hot_memory import HotMemory
from src.utils.config import get_config
from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class RetrievalResult:
    query: str
    vector_results: list[MemoryEntry] = field(default_factory=list)
    graph_results: list[Triple] = field(default_factory=list)
    fused_results: list[Any] = field(default_factory=list)
    context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


class MemoryRetriever:
    """融合向量语义搜索和知识图谱查询的记忆检索器"""

    def __init__(self):
        self.config = get_config()
        self.warm = WarmMemory()
        self.hot = HotMemory()

    async def retrieve(
        self,
        query: str,
        session_id: str = "default",
        top_k: int = 5,
        use_vector: bool = True,
        use_graph: bool = True,
        fusion_method: str = "weighted",
    ) -> RetrievalResult:
        """检索相关记忆"""
        logger.info("检索记忆: query=%s", query[:50])

        vector_results = []
        graph_results = []

        if use_vector:
            vector_results = await self.warm.search(query, top_k=top_k)
            logger.info("向量搜索结果: %d 条", len(vector_results))

        if use_graph:
            keywords = query.split()
            for keyword in keywords:
                triples = self.warm.query_triples(subject=keyword)
                graph_results.extend(triples)
                triples = self.warm.query_triples(obj=keyword)
                graph_results.extend(triples)
            graph_results = list({(t.subject, t.predicate, t.obj): t for t in graph_results}.values())
            logger.info("知识图谱查询结果: %d 条", len(graph_results))

        fused = self._fuse_results(vector_results, graph_results, fusion_method)
        context = self._build_context(fused, vector_results, graph_results)

        return RetrievalResult(
            query=query,
            vector_results=vector_results,
            graph_results=graph_results,
            fused_results=fused,
            context=context,
            metadata={"fusion_method": fusion_method, "vector_count": len(vector_results), "graph_count": len(graph_results)},
        )

    def _fuse_results(
        self,
        vector_results: list[MemoryEntry],
        graph_results: list[Triple],
        method: str = "weighted",
    ) -> list[Any]:
        """融合向量和图谱结果"""
        if method == "weighted":
            fused = []
            for entry in vector_results:
                fused.append({"type": "vector", "content": entry.content, "score": entry.relevance_score, "source": entry.source})
            for triple in graph_results:
                fused.append({"type": "triple", "content": f"{triple.subject}-{triple.predicate}-{triple.obj}", "score": triple.confidence})
            fused.sort(key=lambda x: x.get("score", 0), reverse=True)
            return fused
        elif method == "merge":
            return vector_results + graph_results
        else:
            return vector_results

    def _build_context(
        self,
        fused: list[Any],
        vector_results: list[MemoryEntry],
        graph_results: list[Triple],
    ) -> str:
        """构建上下文字符串"""
        parts = []

        if vector_results:
            vector_ctx = "\n".join(f"[语义] {e.content}" for e in vector_results[:3])
            parts.append(f"语义搜索结果:\n{vector_ctx}")

        if graph_results:
            graph_ctx = "\n".join(f"[知识] {t.subject} → {t.predicate} → {t.obj}" for t in graph_results[:5])
            parts.append(f"知识图谱结果:\n{graph_ctx}")

        return "\n\n".join(parts)

    async def retrieve_with_context(
        self,
        query: str,
        session_id: str = "default",
        include_hot: bool = True,
        max_entries: int = 5,
    ) -> str:
        """检索并返回完整上下文（热+温）"""
        result = await self.retrieve(query, session_id, top_k=max_entries)

        hot_context = ""
        if include_hot:
            recent = self.hot.get_recent(5, session_id)
            if recent:
                hot_context = "\n".join(f"[{m.role}] {m.content}" for m in recent)

        parts = []
        if hot_context:
            parts.append(f"对话上下文:\n{hot_context}")
        if result.context:
            parts.append(f"相关知识:\n{result.context}")

        return "\n\n".join(parts)
