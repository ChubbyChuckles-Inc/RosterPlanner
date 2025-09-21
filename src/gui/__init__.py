"""RosterPlanner GUI public API (Milestone 1.1.1).

Curated, intentionally small surface for external callers (CLI bootstrap,
plugin entrypoints, tests) to interact with the GUI layer without depending
on deep internal module paths.

Design Principles:
- Keep exports minimal & stable; prefer namespaced access (e.g. `import gui.design as design`).
- Avoid side-effect heavy imports (no implicit QApplication creation).
- Re-export only foundational infrastructure (service locator, event bus, bootstrap helpers, design namespace).

Future Additions (post milestones):
- High-level `launch_gui()` convenience wrapper
- Version metadata / about dialog accessors
"""

from __future__ import annotations

# Infrastructure
from .services.service_locator import (  # noqa: F401
    services,
    ServiceLocator,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
)
from .services.event_bus import (  # noqa: F401
    EventBus,
    GUIEvent,
    Event,
)

# Application bootstrap helpers (lazy import if present)
try:  # pragma: no cover - optional bootstrap not always used in tests
    from .app.bootstrap import create_application  # type: ignore  # noqa: F401
except Exception:  # pragma: no cover
    create_application = None  # type: ignore

# Expose design system as namespaced module (do not flatten hundreds of symbols)
from . import design  # noqa: F401  (import package so users can: from gui import design)

__all__ = [
    "services",
    "ServiceLocator",
    "ServiceAlreadyRegisteredError",
    "ServiceNotFoundError",
    "EventBus",
    "GUIEvent",
    "Event",
    "create_application",
    "design",
]
