"""工具执行模块 — 执行具体工具调用"""

import asyncio
import subprocess
import sys
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class ToolResult:
    tool_name: str
    success: bool
    output: Any
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class ToolRegistry:
    """工具注册中心"""

    def __init__(self):
        self._tools: dict[str, Callable] = {}
        self._register_defaults()

    def register(self, name: str, func: Callable):
        self._tools[name] = func
        logger.debug("注册工具: %s", name)

    def get(self, name: str) -> Optional[Callable]:
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        return list(self._tools.keys())

    def _register_defaults(self):
        self.register("search", self._tool_search)
        self.register("calculate", self._tool_calculate)
        self.register("code_execute", self._tool_code_execute)

    @staticmethod
    async def _tool_search(query: str) -> str:
        return f"搜索结果: 暂无外部搜索API连接 — 查询: {query}"

    @staticmethod
    async def _tool_calculate(expression: str) -> str:
        import re
        math_expr = re.search(r'[\d\+\-\*\/\(\)\.]+', expression)
        if math_expr:
            expr = math_expr.group()
            try:
                result = eval(expr, {"__builtins__": {}}, {})
                return f"计算结果: {expr} = {result}"
            except Exception as e:
                return f"计算错误: {e}"
        return f"无法从文本中提取数学表达式: {expression}"

    @staticmethod
    async def _tool_code_execute(code: str) -> str:
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-c", code,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
            if proc.returncode == 0:
                return f"执行成功:\n{stdout.decode()}"
            return f"执行失败:\n{stderr.decode()}"
        except asyncio.TimeoutError:
            return "执行超时（30秒限制）"
        except Exception as e:
            return f"执行错误: {e}"


class ToolExecutor:
    """执行工具调用"""

    def __init__(self, registry: Optional[ToolRegistry] = None):
        self.registry = registry or ToolRegistry()

    async def execute(self, tool_name: str, **kwargs) -> ToolResult:
        """执行指定工具"""
        logger.info("执行工具: %s, 参数: %s", tool_name, kwargs)

        func = self.registry.get(tool_name)
        if func is None:
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"未知工具: {tool_name}",
            )

        try:
            if asyncio.iscoroutinefunction(func):
                output = await func(**kwargs)
            else:
                output = func(**kwargs)
            return ToolResult(tool_name=tool_name, success=True, output=output)
        except Exception as e:
            logger.error("工具执行失败: %s — %s", tool_name, e)
            return ToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=str(e),
            )

    async def execute_batch(self, calls: list[dict]) -> list[ToolResult]:
        """批量执行工具调用"""
        tasks = [self.execute(c["tool"], **c.get("kwargs", {})) for c in calls]
        return await asyncio.gather(*tasks)
