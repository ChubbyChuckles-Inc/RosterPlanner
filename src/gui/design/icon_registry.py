"""Icon registry and loader (Milestone 5.10.4 initial pass).

Provides a lightweight singleton-style registry for semantic icon names mapped
to SVG resource paths. For now we load raw SVG bytes on demand and create a
QIcon via QPixmap rendering. This keeps implementation minimal and avoids
introducing extra dependencies.

Future enhancements (remaining for full 5.10.4 completion):
 - Theming (recoloring via token-aware recolor pass)
 - Caching rendered pixmaps at size buckets
 - High DPI multi-size variants
 - Plugin extension hook
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt
from PyQt6.QtSvg import QSvgRenderer  # type: ignore
from PyQt6.QtCore import QByteArray, QSize

_ICON_DIR = Path(__file__).parent / "icons"


@dataclass(frozen=True)
class IconDefinition:
    name: str
    path: Path


class IconRegistry:
    _instance: "IconRegistry" | None = None

    def __init__(self) -> None:  # pragma: no cover - trivial
        self._defs: Dict[str, IconDefinition] = {}
        self._loaded: Dict[tuple[str, int], QIcon] = {}
        self._discover_builtin()

    # Singleton ----------------------------------------------------
    @classmethod
    def instance(cls) -> "IconRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # Discovery ----------------------------------------------------
    def _discover_builtin(self) -> None:
        if not _ICON_DIR.exists():  # pragma: no cover
            return
        for p in _ICON_DIR.glob("*.svg"):
            self._defs[p.stem] = IconDefinition(name=p.stem, path=p)

    # API ----------------------------------------------------------
    def list_icons(self) -> list[str]:
        return sorted(self._defs.keys())

    def register(self, name: str, path: Path) -> None:
        if name in self._defs:  # overwrite allowed for theme packs
            self._defs[name] = IconDefinition(name=name, path=path)
        else:
            self._defs[name] = IconDefinition(name=name, path=path)

    def get_icon(
        self,
        name: str,
        *,
        size: int = 16,
        color: str | None = None,
        multi_tone: bool = False,
        tone_colors: dict[str, str] | None = None,
        state: str = "normal",
    ) -> Optional[QIcon]:
        key: Tuple[str, int, str | None, bool, str] = (name, size, color, multi_tone, state)
        if key in self._loaded:
            return self._loaded[key]
        definition = self._defs.get(name)
        if not definition:
            return None
        try:
            with open(definition.path, "rb") as f:
                data = f.read()
        except OSError:
            return None
        if multi_tone:
            try:
                from .icon_recolor import recolor_svg

                svg_text = data.decode("utf-8", errors="ignore")
                if tone_colors:
                    svg_text = recolor_svg(svg_text, tone_colors, state=state)
                    data = svg_text.encode("utf-8")
            except Exception:  # pragma: no cover - safe fallback to original
                pass
        renderer = QSvgRenderer(QByteArray(data))
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)  # type: ignore
        painter = QPainter(pm)  # type: ignore
        try:
            renderer.render(painter)
        finally:
            painter.end()
        if color:
            # Simple monochrome tint: draw colored rectangle using destination-in composition
            try:
                tint = QColor(color)
                mask = pm.createMaskFromColor(Qt.GlobalColor.transparent, mode=Qt.MaskMode.MaskOutColor)  # type: ignore
                tinted = QPixmap(pm.size())
                tinted.fill(tint)
                tinted.setMask(mask)
                pm = tinted
            except Exception:  # pragma: no cover - best effort
                pass
        icon = QIcon(pm)
        self._loaded[key] = icon
        return icon


def get_icon(
    name: str,
    *,
    size: int = 16,
    color: str | None = None,
    multi_tone: bool = False,
    tone_colors: dict[str, str] | None = None,
    state: str = "normal",
) -> Optional[QIcon]:
    return IconRegistry.instance().get_icon(
        name, size=size, color=color, multi_tone=multi_tone, tone_colors=tone_colors, state=state
    )


__all__ = ["IconRegistry", "get_icon", "IconDefinition"]
