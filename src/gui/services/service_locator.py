"""Basic service locator / dependency container.

This module provides a minimal, test-friendly registry for application-wide services.
It is intentionally simple to avoid premature complexity while enabling:
- Central registration of shared singletons (repositories, event bus, theme manager, etc.).
- Late binding / override in tests.
- Guardrails against accidental double-registration (unless explicitly allowed).

Usage pattern:
    from gui.services.service_locator import services
    services.register('event_bus', EventBus())
    bus = services.get('event_bus')

In tests:
    services.override('event_bus', FakeEventBus())

Design notes:
- Keys are strings (semantic names). Could be upgraded later to typed keys / Protocol-based retrieval.
- Thread-safety: a simple RLock protects registry; overhead negligible for expected call frequency.
- Lifecycle: No automatic disposal; long-lived process with occasional test resets.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any, Dict, Iterable, Type, TypeVar, Generator, Callable
from contextlib import contextmanager

T = TypeVar("T")

__all__ = ["ServiceLocator", "services", "ServiceAlreadyRegisteredError", "ServiceNotFoundError"]


class ServiceAlreadyRegisteredError(RuntimeError):
    """Raised when attempting to register an existing key without allow_override."""


class ServiceNotFoundError(KeyError):
    """Raised when a requested service key is not present."""


@dataclass
class ServiceRecord:
    key: str
    value: Any
    origin: str | None = None  # optional metadata (e.g., module path)


class ServiceLocator:
    """Thread-safe service registry."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._services: Dict[str, ServiceRecord] = {}

    def register(
        self, key: str, value: Any, *, allow_override: bool = False, origin: str | None = None
    ) -> None:
        """Register a service object.

        Parameters
        ----------
        key : str
            Unique service identifier.
        value : Any
            The service instance.
        allow_override : bool
            If False, raises if key already exists; if True, overwrites.
        origin : str | None
            Optional metadata (e.g., module registering this value).
        """
        with self._lock:
            if key in self._services and not allow_override:
                raise ServiceAlreadyRegisteredError(f"Service '{key}' already registered")
            self._services[key] = ServiceRecord(key=key, value=value, origin=origin)

    def get(self, key: str) -> Any:
        with self._lock:
            record = self._services.get(key)
            if record is None:
                raise ServiceNotFoundError(key)
            return record.value

    def get_typed(self, key: str, expected_type: Type[T]) -> T:
        """Retrieve a service and assert it matches expected_type.

        Raises TypeError with a clear message if mismatch.
        """
        value = self.get(key)
        if not isinstance(value, expected_type):
            raise TypeError(
                f"Service '{key}' expected type {expected_type!r} but got {type(value)!r}"
            )
        return value

    def try_get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            record = self._services.get(key)
            return record.value if record else default

    def override(self, key: str, value: Any) -> None:
        with self._lock:
            if key not in self._services:
                raise ServiceNotFoundError(key)
            self._services[key] = ServiceRecord(key=key, value=value, origin="override")

    @contextmanager
    def override_context(self, **overrides: Any) -> Generator[None, None, None]:
        """Temporarily override one or more services within a context.

        Example:
            with services.override_context(event_bus=FakeBus()):
                ... test code ...
        Restores previous values (if present) on exit.
        """
        previous: Dict[str, ServiceRecord | None] = {}
        with self._lock:
            for key, new_value in overrides.items():
                previous[key] = self._services.get(key)
                if key not in self._services:
                    # Register new ephemeral service
                    self._services[key] = ServiceRecord(key=key, value=new_value, origin="temp")
                else:
                    self._services[key] = ServiceRecord(key=key, value=new_value, origin="override")
        try:
            yield
        finally:
            with self._lock:
                for key, prior in previous.items():
                    if prior is None:
                        # Was created ephemeral; remove
                        self._services.pop(key, None)
                    else:
                        self._services[key] = prior

    def unregister(self, key: str) -> None:
        with self._lock:
            if key in self._services:
                del self._services[key]

    def list_keys(self) -> Iterable[str]:
        with self._lock:
            return list(self._services.keys())

    def clear(self) -> None:
        with self._lock:
            self._services.clear()


# Global instance (acceptable for this controlled scope; can be replaced later with hierarchical containers)
services = ServiceLocator()
