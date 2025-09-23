"""Utilities for applying theme QSS with performance instrumentation.

This extracts the timing + warning logic from the GUI MainWindow so it can be
unit tested without requiring a QApplication / QWidget instance. The caller
provides a lightweight object implementing ``styleSheet()`` and
``setStyleSheet(str)``.
"""

from __future__ import annotations

from typing import Protocol, Optional, Tuple
import time
import sys


class _StyleHost(Protocol):  # pragma: no cover - structural protocol
    def styleSheet(self) -> str: ...  # noqa: D401,E701 - protocol signature only
    def setStyleSheet(self, qss: str) -> None: ...  # noqa: D401,E701


def apply_theme_qss(
    host: _StyleHost,
    qss: str,
    *,
    event_bus: Optional[object] = None,
    threshold_ms: float = 50.0,
    emit_trace: bool = True,
) -> Tuple[float, bool]:
    """Apply (merge/replace) a generated theme QSS onto a host object.

    Returns (duration_ms, warning_emitted).
    """
    start = time.perf_counter()
    try:
        current = host.styleSheet()  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        current = ""
    marker = "/* THEME (auto-generated runtime) */"
    if marker in current:
        pre = current.split(marker)[0].rstrip()
        new_sheet = (pre + "\n" + qss) if pre else qss
    else:
        new_sheet = (current + "\n" + qss) if current else qss
    try:
        host.setStyleSheet(new_sheet)  # type: ignore[attr-defined]
    except Exception:  # pragma: no cover - defensive
        pass
    duration_ms = (time.perf_counter() - start) * 1000.0
    warned = False
    if duration_ms > threshold_ms:
        warned = True
        payload = {"duration_ms": duration_ms}
        if event_bus is not None:
            try:  # publish best-effort
                getattr(event_bus, "publish")("THEME_STYLE_APPLY_SLOW", payload)  # type: ignore
            except Exception:  # pragma: no cover
                pass
        # Always have a fallback textual signal
        try:
            print(
                f"[theme-style-apply-warning] took {duration_ms:.2f}ms (> {threshold_ms}ms)",
                file=sys.stdout,
            )
        except Exception:  # pragma: no cover
            pass
    if emit_trace:
        try:
            print(f"[theme-style-apply] {duration_ms:.2f}ms", file=sys.stdout)
        except Exception:  # pragma: no cover
            pass
    return duration_ms, warned


__all__ = ["apply_theme_qss"]
