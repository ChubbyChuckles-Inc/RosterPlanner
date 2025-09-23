"""Dynamic accent extraction (Milestone 5.10.23).

Lightweight color quantization spike to derive a representative accent color
from an image (e.g., club logo, division banner). Avoids heavy dependencies by
operating on raw pixel data provided by caller (list of RGB tuples) or by
accepting a small PIL Image if Pillow is available at runtime (optional).

Approach:
 - Downsample (limit pixels) for performance.
 - Apply a simplified median-cut style bucket partition until target palette
   size reached or cannot further split.
 - Score buckets by (population * saturation * value) to bias towards vivid
   usable accents while avoiding extreme near-grayscale.
 - Return hex string of top candidate along with secondary suggestions.

This is intentionally modest; future expansion could integrate k-means or
perceptual color space conversions (Lab) if needed. Unit tests validate basic
extraction on synthetic inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Sequence, Tuple

__all__ = [
    "AccentExtractionResult",
    "extract_accent_from_pixels",
    "extract_accent_from_image",
]

RGB = Tuple[int, int, int]


@dataclass(frozen=True)
class AccentExtractionResult:
    accent: str  # primary accent hex (#RRGGBB)
    palette: List[str]  # additional candidate hex colors (ordered)
    source_count: int  # number of pixels considered post-downsample


def _to_hex(rgb: RGB) -> str:
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"


def _saturation_value(rgb: RGB) -> Tuple[float, float]:
    r, g, b = [c / 255.0 for c in rgb]
    mx = max(r, g, b)
    mn = min(r, g, b)
    delta = mx - mn
    s = 0.0 if mx == 0 else delta / mx
    v = mx
    return s, v


def _score(rgb: RGB, count: int) -> float:
    s, v = _saturation_value(rgb)
    # Bias against extremely dark or light near-grayscale (low S) while
    # still allowing vibrant mid/high value colors.
    if s < 0.05:  # near grayscale
        return 0.0
    return count * (0.4 + 0.6 * s) * (0.5 + 0.5 * v)


def _median_cut(pixels: Sequence[RGB], max_colors: int = 8) -> List[Tuple[RGB, int]]:
    # Each bucket holds (pixels list)
    buckets: List[List[RGB]] = [list(pixels)]
    while len(buckets) < max_colors:
        # Select bucket with largest channel range to split
        buckets.sort(key=lambda b: _bucket_range(b), reverse=True)
        target = buckets[0]
        if len(target) <= 1:
            break
        channel = _bucket_dominant_channel(target)
        target.sort(key=lambda p: p[channel])
        mid = len(target) // 2
        b1 = target[:mid]
        b2 = target[mid:]
        buckets = buckets[1:] + [b1, b2]
    # Represent each bucket by average color
    results: List[Tuple[RGB, int]] = []
    for b in buckets:
        if not b:
            continue
        r = sum(p[0] for p in b) // len(b)
        g = sum(p[1] for p in b) // len(b)
        bl = sum(p[2] for p in b) // len(b)
        results.append(((r, g, bl), len(b)))
    return results


def _bucket_range(bucket: Sequence[RGB]) -> int:
    rs = [p[0] for p in bucket]
    gs = [p[1] for p in bucket]
    bs = [p[2] for p in bucket]
    return (max(rs) - min(rs)) + (max(gs) - min(gs)) + (max(bs) - min(bs))


def _bucket_dominant_channel(bucket: Sequence[RGB]) -> int:
    rs = [p[0] for p in bucket]
    gs = [p[1] for p in bucket]
    bs = [p[2] for p in bucket]
    ranges = [max(rs) - min(rs), max(gs) - min(gs), max(bs) - min(bs)]
    return ranges.index(max(ranges))


def extract_accent_from_pixels(
    pixels: Iterable[RGB],
    *,
    max_pixels: int = 4096,
    palette_size: int = 5,
) -> AccentExtractionResult:
    px_list: List[RGB] = []
    for i, p in enumerate(pixels):
        if i >= max_pixels:
            break
        # Basic clamp/sanitize
        r, g, b = p
        px_list.append((max(0, min(r, 255)), max(0, min(g, 255)), max(0, min(b, 255))))
    if not px_list:
        return AccentExtractionResult(accent="#888888", palette=["#888888"], source_count=0)
    buckets = _median_cut(px_list, max_colors=max(2, palette_size * 2))
    scored = [(_score(rgb, count), rgb, count) for rgb, count in buckets]
    scored.sort(key=lambda t: t[0], reverse=True)
    # Filter zero-score entries (grayscale) but ensure fallback if all zero
    nonzero = [t for t in scored if t[0] > 0]
    ranked = nonzero if nonzero else scored
    palette: List[str] = []
    for _score_v, rgb, _cnt in ranked[:palette_size]:
        palette.append(_to_hex(rgb))
    accent = palette[0]
    return AccentExtractionResult(accent=accent, palette=palette, source_count=len(px_list))


def extract_accent_from_image(img) -> AccentExtractionResult:  # pragma: no cover - thin wrapper
    try:
        # Lazy import Pillow if present
        from PIL import Image  # type: ignore
    except Exception:  # Pillow not installed
        raise RuntimeError("Pillow not available; pass pixels directly")  # noqa: EM101
    if not isinstance(img, Image.Image):  # type: ignore[attr-defined]
        raise TypeError("Expected PIL.Image.Image instance")
    # Convert to RGB and downscale large images for performance
    small = img.convert("RGB")
    max_side = max(small.size)
    if max_side > 256:
        ratio = 256 / max_side
        new_size = (int(small.size[0] * ratio), int(small.size[1] * ratio))
        small = small.resize(new_size)
    pixels = list(small.getdata())
    return extract_accent_from_pixels(pixels)
