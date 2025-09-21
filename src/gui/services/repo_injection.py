"""Repository injection helpers (Milestone 1.4.1).

Provides a thin convenience layer over the global service locator for
registering and temporarily overriding data repositories in tests.

Key conventions:
- Repository service keys are prefixed with 'repo:' followed by a short name
  (e.g., 'repo:team', 'repo:player').
- `register_repo(name, repo)` registers a repository (idempotent with allow_override flag).
- `get_repo(name, expected_type=None)` retrieves a repository optionally performing
  a runtime isinstance check.
- `inject_repos(**repos)` is a context manager allowing temporary overrides for tests.

Rationale:
Centralizing repository key construction reduces risk of typos and eases future
refactors (e.g., moving to a more structured dependency graph).
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Dict, Generator, Optional, Type, TypeVar

from .service_locator import services, ServiceNotFoundError

__all__ = [
    "repo_key",
    "register_repo",
    "get_repo",
    "inject_repos",
]

T = TypeVar("T")


def repo_key(name: str) -> str:
    return f"repo:{name}".lower()


def register_repo(name: str, repo: Any, *, allow_override: bool = True) -> None:
    services.register(repo_key(name), repo, allow_override=allow_override)


def get_repo(name: str, expected_type: Optional[Type[T]] = None) -> T | Any:
    value = services.get(repo_key(name))
    if expected_type is not None and not isinstance(value, expected_type):
        raise TypeError(
            f"Repository '{name}' expected type {expected_type!r} but got {type(value)!r}"
        )
    return value


@contextmanager
def inject_repos(**repos: Any) -> Generator[None, None, None]:
    translated = {repo_key(k): v for k, v in repos.items()}
    with services.override_context(**translated):
        yield
