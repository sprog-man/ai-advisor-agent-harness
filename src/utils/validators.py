"""数据验证模块"""

from typing import Any


def validate_user_input(text: Any) -> str:
    if not isinstance(text, str):
        raise TypeError(f"输入必须是字符串，收到 {type(text).__name__}")
    text = text.strip()
    if not text:
        raise ValueError("输入不能为空")
    if len(text) > 10000:
        raise ValueError("输入长度超过限制（10000字符）")
    return text


def validate_task_list(tasks: Any) -> list:
    if not isinstance(tasks, list):
        raise TypeError("任务列表必须是列表类型")
    for i, task in enumerate(tasks):
        if not isinstance(task, dict):
            raise TypeError(f"任务 {i} 必须是字典类型")
        if "description" not in task:
            raise KeyError(f"任务 {i} 缺少 description 字段")
    return tasks
