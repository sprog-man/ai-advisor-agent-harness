"""真实API集成测试"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Windows终端UTF-8支持
if sys.platform == "win32":
    os.system("chcp 65001 >nul 2>&1")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from src.utils.config import load_config
from src.core.intent_parser import IntentParser
from src.core.task_decomposer import TaskDecomposer
from src.core.summarizer import Summarizer


async def test_intent_parser():
    print("=" * 50)
    print("测试1: 意图解析 (真实API)")
    print("=" * 50)

    config = load_config()
    print(f"API: {config.llm.base_url}")
    print(f"模型: {config.llm.model}")

    parser = IntentParser()
    result = await parser.parse("帮我分析一下Python和Java哪个更适合做Web后端开发")

    print(f"意图类型: {result.intent_type.value}")
    print(f"置信度: {result.confidence}")
    print(f"关键词: {result.keywords}")
    print(f"元数据: {result.metadata}")
    print()
    return result


async def test_task_decomposer(intent):
    print("=" * 50)
    print("测试2: 任务拆解 (真实API)")
    print("=" * 50)

    decomposer = TaskDecomposer()
    plan = await decomposer.decompose(intent)

    print(f"拆解理由: {plan.reasoning}")
    print(f"子任务数: {len(plan.sub_tasks)}")
    for task in plan.sub_tasks:
        print(f"  - [{task.priority.value}] {task.description}")
        print(f"    工具: {task.tools_needed}")
    print()
    return plan


async def test_summarizer(intent, plan):
    print("=" * 50)
    print("测试3: 总结生成 (真实API)")
    print("=" * 50)

    from src.core.tool_executor import ToolResult

    mock_results = [
        ToolResult(
            tool_name="search",
            success=True,
            output="Python Web框架: Django, Flask, FastAPI. Java Web框架: Spring Boot, Jakarta EE. Python适合快速开发，Java适合企业级应用。",
        )
    ]

    summarizer = Summarizer()
    summary = await summarizer.summarize(
        intent, plan.sub_tasks, mock_results, "Python适合初创公司和快速迭代，Java适合大型企业和高并发场景"
    )

    print(f"总结内容:\n{summary.content}")
    print(f"数据源: {summary.sources}")
    print()


async def main():
    print("AI Advisor Agent — 真实API集成测试")
    print()

    try:
        intent = await test_intent_parser()
        plan = await test_task_decomposer(intent)
        await test_summarizer(intent, plan)
        print("所有测试通过!")
    except Exception as e:
        print(f"测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
