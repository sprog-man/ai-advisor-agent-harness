"""AI Advisor Agent — 主入口"""

import asyncio

from src.orchestrator import Orchestrator


async def main():
    """交互式命令行入口"""
    print("=" * 50)
    print("  AI Advisor Agent")
    print("  输入 'quit' 或 'exit' 退出")
    print("=" * 50)

    orchestrator = Orchestrator()

    while True:
        try:
            user_input = input("\n你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见！")
            break

        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见！")
            break

        result = await orchestrator.run(user_input)
        print(f"\nAI: {result.summary.content}")


if __name__ == "__main__":
    asyncio.run(main())
