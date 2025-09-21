"""Token metadata annotation (Milestone 0.43).

Provides a lightweight in-memory registry for design token metadata:
 - Usage counts (incremented by tooling / build steps / runtime instrumentation)
 - Deprecation flags with optional replacement suggestions & rationale

Non-goals (kept intentionally simple for now):
 - Persistent storage (could be serialized later to JSON for reporting)
 - Automatic discovery of unused tokens (would require global static analysis)

Public API:
    annotate_usage(token_key: str, count: int = 1)
    mark_deprecated(token_key: str, *, replacement: str | None = None, reason: str | None = None)
    get_metadata(token_key: str) -> TokenMetadata | None
    list_metadata() -> tuple[TokenMetadata, ...]
    list_deprecated() -> tuple[TokenMetadata, ...]
    clear_metadata()

Implementation details:
 - Token keys are expected to be flattened dot-notation keys, consistent with
   ``token_changelog.flatten_tokens``. A helper ``flatten_design_tokens`` is
   provided to flatten a ``DesignTokens`` instance to validate existence.
 - Unknown token keys raise ``KeyError`` to fail fast and avoid silent drift.
 - Thread-safety is not required at this stage (single-threaded GUI context);
   can be wrapped with a lock later if needed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Any, Mapping, Iterable, Tuple

try:  # Optional import; fall back if not available during very early bootstrap.
    from .loader import DesignTokens  # type: ignore
except Exception:  # pragma: no cover - loader absent only in edge bootstrap

    class DesignTokens:  # type: ignore
        raw: Mapping[str, Any]


__all__ = [
    "TokenMetadata",
    "annotate_usage",
    "mark_deprecated",
    "get_metadata",
    "list_metadata",
    "list_deprecated",
    "clear_metadata",
    "flatten_design_tokens",
]


@dataclass
class TokenMetadata:
    key: str
    usage_count: int = 0
    deprecated: bool = False
    replacement: str | None = None
    reason: str | None = None
    # History of incremental usage annotations (could store timestamps later)
    usage_events: list[int] = field(default_factory=list)

    def record_usage(self, count: int) -> None:
        self.usage_count += count
        self.usage_events.append(count)

    def deprecate(self, replacement: str | None, reason: str | None) -> None:
        self.deprecated = True
        self.replacement = replacement
        self.reason = reason


_REGISTRY: Dict[str, TokenMetadata] = {}
_KNOWN_KEYS: set[str] = set()  # Populated on first validation call.


def flatten_design_tokens(tokens: "DesignTokens") -> Iterable[str]:
    """Flatten token keys from a ``DesignTokens`` instance.

    This mirrors logic in token_changelog.flatten_tokens but only returns keys
    for existence validation; values are irrelevant here.
    """

    def _walk(node: Any, prefix: str = "") -> Iterable[str]:
        if isinstance(node, Mapping):
            for k, v in node.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, Mapping) or isinstance(v, list):
                    yield from _walk(v, new_prefix)
                else:
                    yield new_prefix
        elif isinstance(node, list):
            for idx, v in enumerate(node):
                new_prefix = f"{prefix}.{idx}" if prefix else str(idx)
                if isinstance(v, (Mapping, list)):
                    yield from _walk(v, new_prefix)
                else:
                    yield new_prefix
        else:  # Primitive root (unlikely for design tokens)
            if prefix:
                yield prefix

    yield from _walk(tokens.raw)


def _ensure_known_keys(tokens: "DesignTokens" | None) -> None:
    if _KNOWN_KEYS:
        return
    if tokens is None:
        raise RuntimeError(
            "Token metadata registry requires a DesignTokens instance for initialisation"
        )
    for k in flatten_design_tokens(tokens):
        _KNOWN_KEYS.add(k)


def _validate_key(token_key: str) -> None:
    if token_key not in _KNOWN_KEYS:
        raise KeyError(f"Unknown design token key: {token_key}")


def annotate_usage(
    token_key: str, *, count: int = 1, tokens: "DesignTokens" | None = None
) -> TokenMetadata:
    """Increment usage count for a token.

    The first call must provide a ``tokens`` instance to seed known keys.
    Subsequent calls can omit it.
    """
    _ensure_known_keys(tokens)
    _validate_key(token_key)
    meta = _REGISTRY.get(token_key)
    if not meta:
        meta = TokenMetadata(key=token_key)
        _REGISTRY[token_key] = meta
    meta.record_usage(count)
    return meta


def mark_deprecated(
    token_key: str,
    *,
    replacement: str | None = None,
    reason: str | None = None,
    tokens: "DesignTokens" | None = None,
) -> TokenMetadata:
    """Mark a token as deprecated with optional replacement & reason."""
    _ensure_known_keys(tokens)
    _validate_key(token_key)
    meta = _REGISTRY.get(token_key)
    if not meta:
        meta = TokenMetadata(key=token_key)
        _REGISTRY[token_key] = meta
    meta.deprecate(replacement, reason)
    return meta


def get_metadata(token_key: str) -> TokenMetadata | None:
    return _REGISTRY.get(token_key)


def list_metadata() -> Tuple[TokenMetadata, ...]:
    return tuple(sorted(_REGISTRY.values(), key=lambda m: m.key))


def list_deprecated() -> Tuple[TokenMetadata, ...]:
    return tuple(m for m in list_metadata() if m.deprecated)


def clear_metadata() -> None:
    _REGISTRY.clear()
    _KNOWN_KEYS.clear()
