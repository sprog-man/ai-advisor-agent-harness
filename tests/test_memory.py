"""三层记忆架构测试"""

import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from src.memory.hot_memory import HotMemory, Message
from src.memory.cold_memory import ColdMemory, RawRecord
from src.memory.warm_memory import WarmMemory, Triple
from src.memory.memory_manager import MemoryManager


class TestHotMemory:
    def setup_method(self):
        self.hot = HotMemory(max_messages=10)

    def test_add_message(self):
        msg = self.hot.add_message("user", "hello")
        assert msg.role == "user"
        assert msg.content == "hello"
        assert self.hot.message_count() == 1

    def test_get_recent(self):
        for i in range(5):
            self.hot.add_message("user", f"msg_{i}")
        recent = self.hot.get_recent(3)
        assert len(recent) == 3
        assert recent[0].content == "msg_2"

    def test_max_messages_limit(self):
        for i in range(15):
            self.hot.add_message("user", f"msg_{i}")
        assert self.hot.message_count() == 10

    def test_get_full_context(self):
        self.hot.add_message("user", "hi")
        self.hot.add_message("assistant", "hello")
        ctx = self.hot.get_full_context()
        assert len(ctx) == 2
        assert ctx[0]["role"] == "user"

    def test_clear(self):
        self.hot.add_message("user", "test")
        self.hot.clear()
        assert self.hot.message_count() == 0

    def test_estimate_tokens(self):
        self.hot.add_message("user", "你好世界")  # 4 chars * 2 = 8 tokens
        tokens = self.hot.estimate_tokens()
        assert tokens == 8


class TestColdMemory:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.cold = ColdMemory(storage_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    def test_store_and_retrieve(self):
        record = RawRecord(
            record_type="conversation",
            content={"role": "user", "content": "test"},
        )
        record_id = self.cold.store(record)
        assert record_id is not None

        results = self.cold.retrieve(record_type="conversation")
        assert len(results) == 1
        assert results[0]["content"]["content"] == "test"

    def test_count(self):
        for i in range(3):
            self.cold.store(RawRecord(record_type="conversation", content=f"msg_{i}"))
        assert self.cold.count("conversation") == 3

    def test_get_by_id(self):
        record = RawRecord(record_type="knowledge", content="fact")
        record_id = self.cold.store(record)
        found = self.cold.get_by_id(record_id)
        assert found is not None
        assert found["content"] == "fact"


class TestWarmMemory:
    def setup_method(self):
        self.warm = WarmMemory()

    def test_add_triple(self):
        triple = Triple(subject="Python", predicate="is", obj="programming language")
        self.warm.add_triple(triple)
        assert len(self.warm._triples) == 1

    def test_query_triples(self):
        self.warm.add_triple(Triple(subject="Python", predicate="is", obj="language"))
        self.warm.add_triple(Triple(subject="Java", predicate="is", obj="language"))
        self.warm.add_triple(Triple(subject="Python", predicate="has", obj="GIL"))

        results = self.warm.query_triples(subject="Python")
        assert len(results) == 2

        results = self.warm.query_triples(predicate="is")
        assert len(results) == 2


class TestMemoryManager:
    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.manager = MemoryManager()
        self.manager.cold = ColdMemory(storage_dir=self.temp_dir)

    def teardown_method(self):
        shutil.rmtree(self.temp_dir)

    @pytest.mark.asyncio
    async def test_record_conversation(self):
        msg = await self.manager.record_conversation("user", "hello", "test_session")
        assert msg.role == "user"
        assert self.manager.hot.message_count("test_session") == 1

    @pytest.mark.asyncio
    async def test_get_stats(self):
        await self.manager.record_conversation("user", "test")
        stats = self.manager.get_stats()
        assert stats["hot_messages"] == 1
        assert stats["cold_records"] >= 1

    def test_clear_session(self):
        self.manager.clear_session()
        assert self.manager.hot.message_count() == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
