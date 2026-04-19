from __future__ import annotations

from dataclasses import dataclass
from time import time

from .models import CommandAction


@dataclass
class Permission:
    path_prefix: str
    action: CommandAction
    expires_at: float

    def is_valid(self) -> bool:
        return time() < self.expires_at

    def matches(self, path: str, action: CommandAction) -> bool:
        return self.is_valid() and action == self.action and path.startswith(self.path_prefix)


class PermissionService:
    def __init__(self) -> None:
        self._permissions: list[Permission] = []
        self._unlocked: dict[str, float] = {}

    def has_permission(self, path: str, action: CommandAction) -> bool:
        self._cleanup()
        return any(p.matches(path, action) for p in self._permissions)

    def grant_path_permission(self, path_prefix: str, action: CommandAction, duration_seconds: int = 900) -> None:
        self._permissions.append(Permission(path_prefix=path_prefix, action=action, expires_at=time() + duration_seconds))

    def unlock_protected_path(self, path: str, duration_seconds: int = 3600) -> None:
        self._unlocked[path] = time() + duration_seconds

    def is_protected_path_unlocked(self, path: str) -> bool:
        self._cleanup()
        expires = self._unlocked.get(path)
        return bool(expires and expires > time())

    def _cleanup(self) -> None:
        now = time()
        self._permissions = [p for p in self._permissions if p.expires_at > now]
        self._unlocked = {k: v for k, v in self._unlocked.items() if v > now}
