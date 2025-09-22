"""Permission Service (Milestone 4.5.1)

Placeholder for future multi-user role-based permissions. For now provides a
simple allow-all policy with hooks so future roles (e.g., viewer, editor,
admin) can restrict actions like export, copy identifiers, or opening detail
views.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict

__all__ = ["PermissionService", "PermissionContext"]


@dataclass
class PermissionContext:
    """Context for evaluating a permission.

    Attributes:
        actor_role: A simple string role placeholder (e.g., "admin", "editor", "viewer").
        resource_kind: Type of resource (e.g., "team").
        action: The action being performed (e.g., "open", "export", "copy_id").
    """

    actor_role: str = "admin"
    resource_kind: str = "team"
    action: str = "open"


class PermissionService:
    """Evaluates whether an action is permitted.

    Current implementation: allow all actions. Structure enables future
    extension (mapping roles to denied/allowed actions). Kept intentionally
    lightweight and synchronous.
    """

    def __init__(self):
        # Future: load role policy from settings or DB
        self._role_matrix: Dict[str, Dict[str, bool]] = {}

    def is_allowed(self, ctx: PermissionContext) -> bool:
        role_policy = self._role_matrix.get(ctx.actor_role)
        if role_policy is None:
            return True  # default allow
        return role_policy.get(ctx.action, True)

    # Convenience wrappers (future granular expansion) -------------
    def can_open_team(self, role: str = "admin") -> bool:
        return self.is_allowed(PermissionContext(actor_role=role, action="open"))

    def can_copy_team_id(self, role: str = "admin") -> bool:
        return self.is_allowed(PermissionContext(actor_role=role, action="copy_id"))

    def can_export_team(self, role: str = "admin") -> bool:
        return self.is_allowed(PermissionContext(actor_role=role, action="export"))
