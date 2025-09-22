"""Parser registry for plugin-based parsers.

This small service allows registering parser callables under a name, running
all registered parsers with protections so a failing parser does not prevent
others from executing. Designed to be lightweight and easily testable.
"""

from __future__ import annotations

from typing import Any, Callable, Dict


class ParserRegistry:
    """Registry to hold parser callables.

    Parsers are callables that accept arbitrary args/kwargs and return any
    serializable result. The registry isolates exceptions from individual
    parsers and returns a per-parser status mapping.
    """

    def __init__(self) -> None:
        self._parsers: Dict[str, Callable[..., Any]] = {}

    def register(self, name: str, parser: Callable[..., Any]) -> None:
        """Register a parser under `name`. Overwrites existing entry.

        Args:
            name: Unique name for the parser.
            parser: Callable to execute during runs.
        """
        self._parsers[name] = parser

    def unregister(self, name: str) -> None:
        """Remove a registered parser; noop if missing."""
        self._parsers.pop(name, None)

    def get_parsers(self) -> Dict[str, Callable[..., Any]]:
        """Return a shallow copy of registered parsers."""
        return dict(self._parsers)

    def run_all(self, *args, **kwargs) -> Dict[str, Dict[str, Any]]:
        """Execute all parsers, returning a status dict per parser.

        Returns a mapping:
            { name: { 'success': bool, 'result': Any (if success), 'exception': str (if failed) } }
        """
        results: Dict[str, Dict[str, Any]] = {}
        for name, parser in list(self._parsers.items()):
            try:
                res = parser(*args, **kwargs)
                results[name] = {"success": True, "result": res}
            except Exception as exc:  # pragma: no cover - tested via unit test
                results[name] = {"success": False, "exception": str(exc)}
        return results


# Convenience singleton for application use
registry = ParserRegistry()
