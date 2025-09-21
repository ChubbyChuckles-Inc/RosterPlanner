"""Visual regression harness utilities.

Provides lightweight primitives to:
- Capture a QPixmap/QImage of a QWidget (offscreen compatible if using 'offscreen' platform)
- Encode to PNG bytes deterministically
- Hash image bytes (SHA256) for stable baselines
- Compare against stored baselines (hash or raw image) and optionally update

Design Goals:
- Avoid heavy dependencies (no PIL required; rely on Qt only when actually capturing)
- Keep pure-Python portions importable without Qt present (facilitate unit tests that mock)
- Deterministic PNG encoding (Qt's save routine is stable for identical pixels)

Baseline Storage Strategy:
We store both the PNG bytes and a companion JSON metadata file (hash, dimensions).
Structure:
  tests/_visual_baseline/<test_name>/<case_name>.png
  tests/_visual_baseline/<test_name>/<case_name>.json

This keeps repo noise scoped and enables future diff image generation.

Future Extensions:
- Pixel diff & heatmap generation
- Perceptual diff thresholds (SSIM)
- Automatic pruning of orphaned baselines
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Optional

__all__ = [
    "capture_widget_screenshot",
    "hash_image_bytes",
    "compare_or_update_baseline",
    "VisualDiffResult",
]

BASELINE_ROOT = Path("tests/_visual_baseline")


def _require_qt():  # Lazy import helper
    try:  # pragma: no cover - import guard logic trivial
        from PyQt6.QtWidgets import QWidget
        from PyQt6.QtGui import QPixmap
        from PyQt6.QtCore import QSize
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError("PyQt6 required for visual capture") from exc
    return QWidget, QPixmap, QSize


def capture_widget_screenshot(widget_factory, *, size: Optional[tuple[int, int]] = None) -> bytes:
    """Instantiate a QWidget via factory and return PNG bytes.

    widget_factory: Callable returning a QWidget
    size: optional (w, h) to force a resize before grabbing
    """
    QWidget, QPixmap, QSize = _require_qt()
    widget = widget_factory()
    if not isinstance(widget, QWidget):  # pragma: no cover - defensive
        raise TypeError("Factory did not return QWidget instance")
    if size:
        widget.resize(*size)
    widget.show()  # Required for proper polish/layout
    # Process events to ensure layout done
    try:
        from PyQt6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:  # pragma: no branch
            app.processEvents()
    except Exception:  # noqa: BLE001
        pass
    pixmap = widget.grab()
    ba = pixmap.toImage()
    # Convert to PNG bytes
    from PyQt6.QtCore import QBuffer, QByteArray

    buff = QBuffer()
    buff.open(QBuffer.OpenModeFlag.ReadWrite)
    ba.save(buff, b"PNG")
    data: bytes = bytes(buff.data())
    buff.close()
    widget.close()
    return data


def hash_image_bytes(data: bytes) -> str:
    return sha256(data).hexdigest()


@dataclass
class VisualDiffResult:
    matched: bool
    baseline_hash: Optional[str]
    new_hash: str
    updated: bool = False
    baseline_path: Optional[Path] = None
    reason: str = ""


def compare_or_update_baseline(
    test_name: str, case_name: str, image_bytes: bytes, *, update: bool = False
) -> VisualDiffResult:
    """Compare screenshot bytes with stored baseline; optionally update baseline.

    Returns VisualDiffResult; when update=True baseline is replaced/created.
    """
    test_dir = BASELINE_ROOT / test_name
    test_dir.mkdir(parents=True, exist_ok=True)
    png_path = test_dir / f"{case_name}.png"
    meta_path = test_dir / f"{case_name}.json"
    new_hash = hash_image_bytes(image_bytes)

    if not png_path.exists():
        if update:
            png_path.write_bytes(image_bytes)
            meta_path.write_text(f'{{\n  "hash": "{new_hash}"\n}}\n', encoding="utf-8")
            return VisualDiffResult(
                False,
                None,
                new_hash,
                updated=True,
                baseline_path=png_path,
                reason="Baseline created",
            )
        return VisualDiffResult(
            False, None, new_hash, updated=False, baseline_path=None, reason="Baseline missing"
        )

    # Load existing hash
    existing_hash: Optional[str] = None
    if meta_path.exists():
        txt = meta_path.read_text(encoding="utf-8")
        # Cheap parse
        marker = '"hash"'
        if marker in txt:
            import re

            m = re.search(r'"hash"\s*:\s*"([0-9a-f]{64})"', txt)
            if m:
                existing_hash = m.group(1)
    if existing_hash is None:
        existing_hash = hash_image_bytes(png_path.read_bytes())

    if existing_hash == new_hash:
        return VisualDiffResult(
            True,
            existing_hash,
            new_hash,
            updated=False,
            baseline_path=png_path,
            reason="Hashes match",
        )

    if update:
        png_path.write_bytes(image_bytes)
        meta_path.write_text(f'{{\n  "hash": "{new_hash}"\n}}\n', encoding="utf-8")
        return VisualDiffResult(
            False,
            existing_hash,
            new_hash,
            updated=True,
            baseline_path=png_path,
            reason="Baseline updated (hash mismatch)",
        )

    return VisualDiffResult(
        False,
        existing_hash,
        new_hash,
        updated=False,
        baseline_path=png_path,
        reason="Hash mismatch",
    )
