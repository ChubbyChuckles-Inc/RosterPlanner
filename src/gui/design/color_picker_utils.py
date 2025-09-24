"""Color picker utilities (Milestone 5.10.60).

Provides pure helper functions to:
 - Normalize / parse hex colors
 - Compute perceptual-ish distance between colors (simple linear RGB delta)
 - Flatten design token color keys
 - Resolve nearest design token color for an arbitrary sampled pixel

The logic is intentionally dependency-free for fast unit testing; distance
metric can be upgraded to CIEDE2000 later if higher fidelity matching is
required. For the current developer overlay use-case a lightweight heuristic
is sufficient: we rank by squared Euclidean distance in sRGB space and apply
deterministic tie‑breaking by sorted token key.
"""

from __future__ import annotations

from typing import Dict, Iterable, Mapping, Tuple

try:  # Optional import guard for early bootstrap / headless tests
    from .loader import DesignTokens, load_tokens  # type: ignore
except Exception:  # pragma: no cover

    class DesignTokens:  # type: ignore
        raw: Mapping[str, object]

    def load_tokens():  # type: ignore
        raise RuntimeError("Design token loader unavailable")


__all__ = [
    "hex_to_rgb",
    "rgb_to_hex",
    "color_distance",
    "flatten_color_tokens",
    "nearest_color_token",
]


def hex_to_rgb(value: str) -> Tuple[int, int, int]:
    """Convert a hex color string (#rrggbb or rrggbb) to an RGB tuple.

    Raises ValueError on malformed input.
    """
    v = value.strip().lower()
    if v.startswith("#"):
        v = v[1:]
    if len(v) == 3:  # short form rgb
        v = "".join(ch * 2 for ch in v)
    if len(v) != 6:
        raise ValueError(f"Invalid hex color: {value}")
    try:
        r = int(v[0:2], 16)
        g = int(v[2:4], 16)
        b = int(v[4:6], 16)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Invalid hex color: {value}") from exc
    return r, g, b


def rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def color_distance(a: Tuple[int, int, int], b: Tuple[int, int, int]) -> int:
    """Return squared Euclidean distance between two RGB tuples.

    Squared distance avoids an unnecessary sqrt while preserving ordering.
    """
    return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2


def flatten_color_tokens(tokens: DesignTokens) -> Dict[str, str]:
    """Flatten only color token keys to mapping of 'color.path.key' -> hex.

    Non-string leaves are ignored defensively.
    """
    result: Dict[str, str] = {}
    color_root = tokens.raw.get("color", {}) if isinstance(tokens.raw, Mapping) else {}

    def _walk(node, prefix: str):
        if isinstance(node, Mapping):
            for k, v in node.items():
                new_prefix = f"{prefix}.{k}" if prefix else k
                if isinstance(v, Mapping):
                    _walk(v, new_prefix)
                else:
                    if isinstance(v, str) and v.startswith("#") and len(v) in (4, 7):
                        result[
                            (
                                f"color.{new_prefix}"
                                if not new_prefix.startswith("color.")
                                else new_prefix
                            )
                        ] = v

    _walk(color_root, "")
    # Deterministic ordering not required for dict but helpful for tie‑breaking in nearest_color_token.
    return result


def nearest_color_token(sample_hex: str, tokens: DesignTokens | None = None):
    """Return (token_key, token_hex, distance) for nearest token color.

    Parameters
    ----------
    sample_hex: str
        Arbitrary input color (supports #rgb, #rrggbb, with/without '#').
    tokens: DesignTokens | None
        Optional explicit token set; if omitted will lazily load via load_tokens().
    """
    if tokens is None:
        tokens = load_tokens()
    sample_rgb = hex_to_rgb(sample_hex)
    flattened = flatten_color_tokens(tokens)
    if not flattened:
        raise ValueError("No color tokens available for matching")
    best_key = None
    best_hex = None
    best_dist = 1_000_000_000
    # Iterate in sorted key order for deterministic tie‑breaking
    for key in sorted(flattened.keys()):
        token_hex = flattened[key]
        try:
            token_rgb = hex_to_rgb(token_hex)
        except ValueError:
            continue
        dist = color_distance(sample_rgb, token_rgb)
        if dist < best_dist or (dist == best_dist and key < (best_key or "")):
            best_key = key
            best_hex = token_hex
            best_dist = dist
            if best_dist == 0:  # exact match early exit
                break
    assert best_key is not None and best_hex is not None  # for type-checkers
    return best_key, best_hex, best_dist
