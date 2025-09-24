"""Reduced Color / Monochrome Mode Service (Milestone 5.10.61).

Provides a minimal service to toggle a reduced-color (grayscale leaning)
mode for the GUI. This helps validate that UI affordances do not rely
solely on hue. The service itself only maintains an in-memory flag and
exposes helpers for converting hex colors to grayscale (luminance) and
generating a small QSS override snippet. Persistence can be added later
via a settings service.
"""

from __future__ import annotations

from typing import Dict, Mapping

__all__ = ["ReducedColorModeService"]


class ReducedColorModeService:
    def __init__(self):
        self._active: bool = False

    # State --------------------------------------------------------
    def set_active(self, active: bool) -> None:
        self._active = bool(active)

    def toggle(self) -> bool:
        self._active = not self._active
        return self._active

    def is_active(self) -> bool:  # pragma: no cover - trivial
        return self._active

    # Conversion ---------------------------------------------------
    @staticmethod
    def grayscale_hex(hex_color: str) -> str:
        c = hex_color.strip()
        if c.startswith("#"):
            c = c[1:]
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            raise ValueError(f"Invalid hex color: {hex_color}")
        try:
            r = int(c[0:2], 16)
            g = int(c[2:4], 16)
            b = int(c[4:6], 16)
        except Exception as exc:  # noqa: BLE001
            raise ValueError(f"Invalid hex digits in {hex_color}") from exc
        y = int(round(0.2126 * r + 0.7152 * g + 0.0722 * b))
        return f"#{y:02x}{y:02x}{y:02x}"

    def transform_mapping(self, colors: Mapping[str, str]) -> Dict[str, str]:
        out: Dict[str, str] = {}
        for k, v in colors.items():
            try:
                out[k] = self.grayscale_hex(v)
            except Exception:
                out[k] = v
        return out

    # QSS ----------------------------------------------------------
    def neutral_qss_snippet(self) -> str:
        if not self._active:
            return ""
        return (
            "/* Reduced Color Mode Overrides */\n"
            'QWidget[reducedColor="1"] QPushButton { background:#4a4a4a; color:#e0e0e0; border:1px solid #666; }\n'
            'QWidget[reducedColor="1"] QLabel { color:#d5d5d5; }\n'
            'QWidget[reducedColor="1"] QTreeView { selection-background-color:#555; }\n'
        )
