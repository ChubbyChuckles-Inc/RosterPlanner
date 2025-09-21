"""Color blindness simulation utilities (Milestone 0.11).

Implements approximate protanopia and deuteranopia simulation using LMS space
matrix transforms (Brettel et al. inspired simplification). Designed for
preview tooling; not intended for clinical accuracy.

If PyQt6 is available, a helper can convert a QImage to a simulated copy.
The core algorithm operates on RGB tuples (0-255) for testability without GUI.
"""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple, Literal

Mode = Literal["protanopia", "deuteranopia"]

__all__ = ["simulate_color_blindness", "simulate_rgb_buffer", "transform_qimage", "Mode"]


# sRGB -> linear helper
def _to_linear(c: float) -> float:
    c = c / 255.0
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> int:
    if c <= 0.0031308:
        v = 12.92 * c
    else:
        v = 1.055 * (c ** (1 / 2.4)) - 0.055
    return int(round(max(0.0, min(1.0, v)) * 255))


# Approximate RGB->LMS and LMS->RGB matrices (Hunt-Pointer-Estevez variant)
_RGB_TO_LMS = (
    (0.31399022, 0.63951294, 0.04649755),
    (0.15537241, 0.75789446, 0.08670142),
    (0.01775239, 0.10944209, 0.87256922),
)
_LMS_TO_RGB = (
    (5.47221206, -4.6419601, 0.16963708),
    (-1.1252419, 2.29317094, -0.1678952),
    (0.02980165, -0.19318073, 1.16364789),
)

# Projection matrices removing L (protan) or M (deutan) channel contribution
_PROTAN_MATRIX = (
    (0.0, 1.05118294, -0.05116099),
    (0.0, 1.0, 0.0),
    (0.0, 0.0, 1.0),
)
_DEUTER_MATRIX = (
    (1.0, 0.0, 0.0),
    (0.9513092, 0.0, 0.04866992),
    (0.0, 0.0, 1.0),
)


def _dot3(
    m: Sequence[Sequence[float]], v: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    return (
        m[0][0] * v[0] + m[0][1] * v[1] + m[0][2] * v[2],
        m[1][0] * v[0] + m[1][1] * v[1] + m[1][2] * v[2],
        m[2][0] * v[0] + m[2][1] * v[1] + m[2][2] * v[2],
    )


def _rgb_to_lms(r: int, g: int, b: int) -> Tuple[float, float, float]:
    lr, lg, lb = _to_linear(r), _to_linear(g), _to_linear(b)
    return _dot3(_RGB_TO_LMS, (lr, lg, lb))


def _lms_to_rgb(l: float, m: float, s: float) -> Tuple[int, int, int]:
    r_lin, g_lin, b_lin = _dot3(_LMS_TO_RGB, (l, m, s))
    return _to_srgb(r_lin), _to_srgb(g_lin), _to_srgb(b_lin)


def simulate_color_blindness(rgb: Tuple[int, int, int], mode: Mode) -> Tuple[int, int, int]:
    """Simulate a single RGB pixel under the specified color blindness mode."""
    l, m, s = _rgb_to_lms(*rgb)
    if mode == "protanopia":
        l, m, s = _dot3(_PROTAN_MATRIX, (l, m, s))
    elif mode == "deuteranopia":
        l, m, s = _dot3(_DEUTER_MATRIX, (l, m, s))
    return _lms_to_rgb(l, m, s)


def simulate_rgb_buffer(
    buffer: Iterable[Tuple[int, int, int]], mode: Mode
) -> List[Tuple[int, int, int]]:
    return [simulate_color_blindness(p, mode) for p in buffer]


def transform_qimage(image, mode: Mode):  # type: ignore[no-untyped-def]
    """Return a transformed QImage copy if PyQt6 is present.

    Accepts a QImage; if PyQt6 not available, raises ImportError.
    Processes via scanLine for performance in small previews; not optimized.
    """
    try:  # Lazy import to keep headless tests safe
        from PyQt6.QtGui import QImage
    except Exception as e:  # pragma: no cover - environment dependent
        raise ImportError("PyQt6 not available for transform_qimage") from e

    if not isinstance(image, QImage):  # pragma: no cover - defensive
        raise TypeError("transform_qimage expects QImage instance")
    img = image.convertToFormat(QImage.Format.Format_RGB32)
    w, h = img.width(), img.height()
    for y in range(h):
        ptr = img.scanLine(y)
        # Access as bytes; convert every pixel
        barray = ptr[: 4 * w]
        new_row = bytearray(barray)
        for x in range(w):
            i = 4 * x
            b, g, r, _a = barray[i], barray[i + 1], barray[i + 2], barray[i + 3]
            nr, ng, nb = simulate_color_blindness((r, g, b), mode)
            new_row[i] = nb
            new_row[i + 1] = ng
            new_row[i + 2] = nr
        # Replace row
        for x in range(len(new_row)):
            ptr[x] = new_row[x]
    return img
