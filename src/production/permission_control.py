"""权限控制模块 — 细粒度权限管理"""

import hashlib
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from src.utils.logger import setup_logger

logger = setup_logger(__name__)


class Permission(Enum):
    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ADMIN = "admin"


class ResourceType(Enum):
    CONVERSATION = "conversation"
    MEMORY = "memory"
    KNOWLEDGE = "knowledge"
    TOOL = "tool"
    SYSTEM = "system"


@dataclass
class Role:
    name: str
    permissions: list[Permission]
    resource_permissions: dict[ResourceType, list[Permission]] = field(default_factory=dict)
    description: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class User:
    user_id: str
    roles: list[str] = field(default_factory=list)
    api_key: Optional[str] = None
    rate_limit: int = 100  # 每分钟请求数
    quota: int = 1000  # 每日配额
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessContext:
    user_id: str
    resource_type: ResourceType
    resource_id: str = ""
    permission: Permission = Permission.READ
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccessResult:
    allowed: bool
    reason: str = ""
    context: Optional[AccessContext] = None
    metadata: dict[str, Any] = field(default_factory=dict)


class PermissionControl:
    """权限控制器"""

    def __init__(self):
        self._roles: dict[str, Role] = {}
        self._users: dict[str, User] = {}
        self._request_counts: dict[str, list[float]] = {}
        self._setup_default_roles()

    def _setup_default_roles(self):
        """设置默认角色"""
        self._roles["viewer"] = Role(
            name="viewer",
            permissions=[Permission.READ],
            resource_permissions={
                ResourceType.CONVERSATION: [Permission.READ],
                ResourceType.MEMORY: [Permission.READ],
                ResourceType.KNOWLEDGE: [Permission.READ],
            },
            description="只读用户",
        )
        self._roles["user"] = Role(
            name="user",
            permissions=[Permission.READ, Permission.WRITE],
            resource_permissions={
                ResourceType.CONVERSATION: [Permission.READ, Permission.WRITE],
                ResourceType.MEMORY: [Permission.READ, Permission.WRITE],
                ResourceType.KNOWLEDGE: [Permission.READ],
                ResourceType.TOOL: [Permission.READ, Permission.EXECUTE],
            },
            description="普通用户",
        )
        self._roles["admin"] = Role(
            name="admin",
            permissions=[Permission.READ, Permission.WRITE, Permission.EXECUTE, Permission.ADMIN],
            description="管理员",
        )

    def register_user(self, user: User):
        """注册用户"""
        self._users[user.user_id] = user
        logger.info("注册用户: %s", user.user_id)

    def add_role(self, role: Role):
        """添加角色"""
        self._roles[role.name] = role

    async def check_access(self, context: AccessContext) -> AccessResult:
        """检查访问权限"""
        user = self._users.get(context.user_id)
        if not user:
            return AccessResult(allowed=False, reason="用户不存在", context=context)

        if not self._check_rate_limit(user):
            return AccessResult(allowed=False, reason="请求频率超限", context=context)

        if not self._check_quota(user):
            return AccessResult(allowed=False, reason="配额已用完", context=context)

        if self._has_permission(user, context.resource_type, context.permission):
            self._record_request(user.user_id)
            return AccessResult(allowed=True, context=context)

        return AccessResult(allowed=False, reason="权限不足", context=context)

    def require_permission(self, resource_type: ResourceType, permission: Permission):
        """装饰器：要求权限"""
        def decorator(func: Callable):
            async def wrapper(*args, **kwargs):
                context = kwargs.get("access_context")
                if context:
                    result = await self.check_access(context)
                    if not result.allowed:
                        raise PermissionError(f"权限不足: {result.reason}")
                return await func(*args, **kwargs)
            return wrapper
        return decorator

    def get_user_permissions(self, user_id: str) -> dict[ResourceType, list[Permission]]:
        """获取用户权限"""
        user = self._users.get(user_id)
        if not user:
            return {}

        permissions: dict[ResourceType, list[Permission]] = {}
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if role:
                for resource_type, perms in role.resource_permissions.items():
                    if resource_type not in permissions:
                        permissions[resource_type] = []
                    permissions[resource_type].extend(perms)
        return permissions

    def _has_permission(self, user: User, resource_type: ResourceType, permission: Permission) -> bool:
        """检查用户是否有权限"""
        for role_name in user.roles:
            role = self._roles.get(role_name)
            if not role:
                continue

            if Permission.ADMIN in role.permissions:
                return True

            if permission in role.permissions:
                return True

            resource_perms = role.resource_permissions.get(resource_type, [])
            if permission in resource_perms:
                return True

        return False

    def _check_rate_limit(self, user: User) -> bool:
        """检查请求频率限制"""
        now = time.time()
        requests = self._request_counts.get(user.user_id, [])
        requests = [r for r in requests if now - r < 60]
        self._request_counts[user.user_id] = requests
        return len(requests) < user.rate_limit

    def _check_quota(self, user: User) -> bool:
        """检查配额"""
        now = datetime.now().date().isoformat()
        today_requests = sum(
            1 for r in self._request_counts.get(user.user_id, [])
            if datetime.fromtimestamp(r).date().isoformat() == now
        )
        return today_requests < user.quota

    def _record_request(self, user_id: str):
        """记录请求"""
        if user_id not in self._request_counts:
            self._request_counts[user_id] = []
        self._request_counts[user_id].append(time.time())

    def get_stats(self) -> dict:
        """获取统计信息"""
        return {
            "users": len(self._users),
            "roles": len(self._roles),
            "requests": {uid: len(reqs) for uid, reqs in self._request_counts.items()},
        }
