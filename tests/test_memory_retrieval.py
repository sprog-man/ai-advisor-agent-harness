"""记忆记录与检索流程测试"""

import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.memory.memory_recorder import MemoryRecorder, ExtractedInfo
from src.memory.memory_retriever import MemoryRetriever, RetrievalResult
from src.memory.warm_memory import Triple


class TestMemoryRecorder:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.recorder = MemoryRecorder()
        self.recorder.cold = __import__('src.memory.cold_memory', fromlist=['ColdMemory']).ColdMemory(storage_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_record_direct(self):
        info = await self.recorder.record_direct(
            content="Python是编程语言",
            facts=["Python是编程语言"],
            triples=[Triple(subject="Python", predicate="是", obj="编程语言")],
        )
        assert info.content == "Python是编程语言"
        assert len(info.facts) == 1

    @pytest.mark.asyncio
    async def test_extract_info_success(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = '{"facts": ["Python是解释型语言"], "triples": [{"subject": "Python", "predicate": "是", "object": "解释型语言", "confidence": 0.9}], "keywords": ["Python"], "entry_type": "fact", "summary": "Python是解释型语言"}'
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.recorder, "_build_llm", return_value=mock_llm):
            with patch.object(self.recorder.warm, "store", new_callable=AsyncMock):
                info = await self.recorder.record_from_text("Python是解释型语言")
                assert len(info.facts) == 1
                assert info.entry_type == "fact"

    @pytest.mark.asyncio
    async def test_extract_info_json_failure(self):
        mock_llm = AsyncMock()
        mock_response = MagicMock()
        mock_response.content = "not json"
        mock_llm.ainvoke.return_value = mock_response

        with patch.object(self.recorder, "_build_llm", return_value=mock_llm):
            info = await self.recorder.record_from_text("test")
            assert info.facts == []


class TestMemoryRetriever:
    def setup_method(self):
        self.retriever = MemoryRetriever()

    @pytest.mark.asyncio
    async def test_retrieve_empty(self):
        result = await self.retriever.retrieve("test query", use_vector=False)
        assert isinstance(result, RetrievalResult)
        assert result.query == "test query"

    @pytest.mark.asyncio
    async def test_retrieve_with_graph(self):
        self.retriever.warm.add_triple(Triple(subject="Python", predicate="是", obj="语言"))
        result = await self.retriever.retrieve("Python", use_vector=False, use_graph=True)
        assert len(result.graph_results) > 0

    @pytest.mark.asyncio
    async def test_fuse_results_weighted(self):
        from src.memory.warm_memory import MemoryEntry
        vector_results = [MemoryEntry(content="test", relevance_score=0.9)]
        graph_results = [Triple(subject="A", predicate="is", obj="B", confidence=0.8)]

        fused = self.retriever._fuse_results(vector_results, graph_results, "weighted")
        assert len(fused) == 2
        assert fused[0]["score"] >= fused[1]["score"]

    @pytest.mark.asyncio
    async def test_build_context(self):
        from src.memory.warm_memory import MemoryEntry
        vector_results = [MemoryEntry(content="test content")]
        graph_results = [Triple(subject="A", predicate="is", obj="B")]

        context = self.retriever._build_context([], vector_results, graph_results)
        assert "语义搜索结果" in context
        assert "知识图谱结果" in context


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
