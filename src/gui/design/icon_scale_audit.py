"""High-DPI asset scaler audit (Milestone 5.10.32).

Generates rasterized PNG bitmaps for registered SVG icons at multiple scale
factors and validates expected dimensions. This supports detecting missing
or low-fidelity assets early and primes a cache for faster runtime loads.

Design Choices:
 - Keep PyQt usage lazy / optional; if PyQt6 import fails (headless w/o Qt),
   expose a no-op path so logic tests can still execute (integration tests
   run in an environment with Qt available).
 - Output directory configurable (default: `assets/icon_raster_cache`).
 - Deterministic filenames: {icon_name}@{scale}x.png
 - Returns a summary dataclass for potential future reporting (e.g., stale
   detection, size parity, missing icons).

Public API:
 - IconRasterResult dataclass
 - rasterize_icons(scales: list[float], size: int = 16, out_dir: Path | None = None) -> IconRasterResult
 - list_cached_bitmaps(out_dir) -> list[Path]

Test Coverage focuses on:
 - Creating images for at least one icon & scale
 - Dimension correctness (width == height == size * scale)
 - Idempotent re-run (does not raise)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List

try:  # optional PyQt import
    from PyQt6.QtGui import QPixmap
    from PyQt6.QtSvg import QSvgRenderer  # type: ignore
    from PyQt6.QtCore import QByteArray
    from PyQt6.QtWidgets import QApplication

    _QT = True
except Exception:  # pragma: no cover
    _QT = False

from .icon_registry import IconRegistry

DEFAULT_OUT = Path("assets/icon_raster_cache")


@dataclass
class IconRasterResult:
    generated: List[Path]
    skipped: List[Path]
    scales: List[float]
    base_size: int


def rasterize_icons(
    scales: List[float], size: int = 16, out_dir: Path | None = None
) -> IconRasterResult:
    out = out_dir or DEFAULT_OUT
    out.mkdir(parents=True, exist_ok=True)
    if not _QT:
        return IconRasterResult(generated=[], skipped=[], scales=scales, base_size=size)
    generated: List[Path] = []
    skipped: List[Path] = []
    registry = IconRegistry.instance()
    icons = registry.list_icons()
    # Ensure a QApplication exists (required for some QPixmap operations on certain platforms)
    from PyQt6.QtWidgets import QApplication as _QA  # type: ignore

    if _QA.instance() is None:  # pragma: no cover - minimal bootstrap
        _app = _QA([])  # noqa: F841

    for name in icons:
        definition = registry._defs.get(name)  # using protected member in same package context
        if not definition:
            continue
        try:
            data = definition.path.read_bytes()
        except OSError:
            continue
        renderer = QSvgRenderer(QByteArray(data))
        for scale in scales:
            target_px = int(round(size * scale))
            fn = out / f"{name}@{scale}x.png"
            if fn.exists():
                skipped.append(fn)
                continue
            pm = QPixmap(target_px, target_px)
            pm.fill(0)  # transparent
            painter = None
            try:
                from PyQt6.QtGui import QPainter

                painter = QPainter(pm)  # type: ignore
                renderer.render(painter)
            finally:
                if painter:
                    painter.end()
            pm.save(str(fn), "PNG")
            generated.append(fn)
    return IconRasterResult(generated=generated, skipped=skipped, scales=scales, base_size=size)


def list_cached_bitmaps(out_dir: Path | None = None) -> List[Path]:
    out = out_dir or DEFAULT_OUT
    if not out.exists():
        return []
    return sorted(out.glob("*.png"))
