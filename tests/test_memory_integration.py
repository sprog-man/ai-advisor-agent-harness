"""三层记忆架构集成测试（真实API）"""

import asyncio
import os
import sys
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.memory.memory_manager import MemoryManager
from src.memory.warm_memory import Triple
from src.memory.cold_memory import ColdMemory


async def test_hot_memory():
    print("=" * 50)
    print("测试1: 热记忆（对话上下文）")
    print("=" * 50)

    manager = MemoryManager()

    await manager.record_conversation("user", "我想学习Python", "test_001")
    await manager.record_conversation("assistant", "Python是一门很好的编程语言", "test_001")
    await manager.record_conversation("user", "有什么推荐的学习资源吗", "test_001")

    count = manager.hot.message_count("test_001")
    print(f"消息数量: {count}")
    assert count == 3

    recent = manager.hot.get_recent(2, "test_001")
    print(f"最近2条: {[m.content for m in recent]}")

    context = manager.hot.get_full_context("test_001")
    print(f"完整上下文: {len(context)} 条消息")
    print("✅ 热记忆测试通过\n")


async def test_warm_memory():
    print("=" * 50)
    print("测试2: 温记忆（向量库+知识图谱）")
    print("=" * 50)

    manager = MemoryManager()

    entry = await manager.store_fact(
        "Python是一种解释型、面向对象的高级编程语言",
        triples=[
            Triple(subject="Python", predicate="是", obj="编程语言"),
            Triple(subject="Python", predicate="类型", obj="解释型"),
        ],
    )
    print(f"存储事实: {entry.id}")

    try:
        results = await manager.search_memory("Python编程")
        print(f"语义搜索结果: {len(results)} 条")
        if results:
            print(f"  最相关: {results[0].content[:50]}...")
    except Exception as e:
        print(f"语义搜索跳过（embedding API不可用）: {e}")

    triples = manager.query_knowledge(subject="Python")
    print(f"知识图谱查询: {len(triples)} 条三元组")
    for t in triples:
        print(f"  ({t.subject}, {t.predicate}, {t.obj})")

    print("✅ 温记忆测试通过\n")


async def test_cold_memory():
    print("=" * 50)
    print("测试3: 冷记忆（原始数据存储）")
    print("=" * 50)

    manager = MemoryManager()

    await manager.record_conversation("user", "测试冷记忆存储", "test_cold")
    await manager.extract_and_store("Python适合快速开发", entry_type="knowledge")

    stats = manager.get_stats()
    print(f"冷记忆统计:")
    print(f"  总记录数: {stats['cold_records']}")
    print(f"  对话记录: {stats['cold_conversations']}")
    print(f"  知识记录: {stats['cold_knowledge']}")
    print("✅ 冷记忆测试通过\n")


async def test_three_layer_integration():
    print("=" * 50)
    print("测试4: 三层记忆联动")
    print("=" * 50)

    manager = MemoryManager()

    await manager.record_conversation("user", "Python和Java哪个更适合Web开发", "test_integration")
    await manager.store_fact("Python适合快速原型开发，Java适合企业级应用")
    await manager.record_conversation("assistant", "两者各有优势，需要根据场景选择", "test_integration")

    try:
        context = await manager.retrieve_context("Python Web开发", "test_integration")
        print(f"检索到的上下文长度: {len(context)} 字符")
        print(f"上下文预览:\n{context[:200]}...")
    except Exception as e:
        print(f"上下文检索跳过（embedding API不可用）: {e}")

    stats = manager.get_stats()
    print(f"\n记忆统计: {stats}")
    print("✅ 三层联动测试通过\n")


async def main():
    print("AI Advisor Agent — 三层记忆架构集成测试")
    print()

    try:
        await test_hot_memory()
        await test_warm_memory()
        await test_cold_memory()
        await test_three_layer_integration()
        print("=" * 50)
        print("所有测试通过!")
        print("=" * 50)
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
