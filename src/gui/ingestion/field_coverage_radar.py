"""Field Coverage Radar Chart (Milestone 7.10.A5)

Provides:
 - Pure logic layer to aggregate a ``FieldCoverageReport`` into coarse semantic
   categories (identity, performance, schedule, meta).
 - A lightweight PyQt6 widget that renders a radar / spider chart of the
   category coverage ratios.

Design Principles
-----------------
* The visual widget is optional – logic functions are importable & testable
  without Qt (guarded imports).
* Category heuristics are intentionally simple string pattern checks so they
  remain deterministic and easy to extend later.
* Hover tooltips list contributing field names + individual ratios to aid
  targeted improvement decisions.

Future Enhancements (deferred)
------------------------------
* Animated transitions on data refresh
* Color scale adapting to theme service
* Export to image / clipboard
* Category customization UI
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Dict, Tuple, TYPE_CHECKING

try:  # pragma: no cover - optional for logic-only test contexts
    from PyQt6.QtWidgets import QWidget, QToolTip
    from PyQt6.QtGui import QPainter, QPen, QColor, QBrush
    from PyQt6.QtCore import Qt, QPointF
except Exception:  # pragma: no cover
    QWidget = object  # type: ignore

if TYPE_CHECKING:  # pragma: no cover - typing only
    from gui.ingestion.rule_field_coverage import FieldCoverageReport  # noqa: F401

__all__ = [
    "CategoryCoverage",
    "categorize_coverage",
    "FieldCoverageRadarWidget",
]


@dataclass
class CategoryCoverage:
    category: str
    fields: List[Tuple[str, float]]  # (field_name, coverage_ratio)

    @property
    def average_ratio(self) -> float:
        if not self.fields:
            return 0.0
        return sum(r for _, r in self.fields) / len(self.fields)

    def tooltip(self) -> str:  # pragma: no cover - simple formatting
        if not self.fields:
            return f"{self.category}: no fields"
        lines = [f"{self.category} ({self.average_ratio:.1%})"]
        for name, ratio in sorted(self.fields, key=lambda x: (-x[1], x[0]))[:14]:
            lines.append(f"  {name}: {ratio:.0%}")
        if len(self.fields) > 14:
            lines.append(f"  … +{len(self.fields) - 14} more")
        return "\n".join(lines)


IDENTITY_TOKENS = {"name", "id", "player", "team", "club"}
PERFORMANCE_TOKENS = {"rating", "match", "points", "wins", "loss", "score"}
SCHEDULE_TOKENS = {"date", "time", "fixture", "round", "week"}


def _classify_field(field_name: str) -> str:
    lower = field_name.lower()
    tokens = {t for t in lower.replace("_", " ").split() if t}
    if tokens & IDENTITY_TOKENS:
        return "identity"
    if tokens & PERFORMANCE_TOKENS:
        return "performance"
    if tokens & SCHEDULE_TOKENS:
        return "schedule"
    return "meta"


def categorize_coverage(report: "FieldCoverageReport") -> List[CategoryCoverage]:
    """Aggregate a FieldCoverageReport into semantic category coverage.

    The aggregation is *field-centric*: each field's individual coverage ratio
    contributes equally to the category average (simple mean).
    """

    category_fields: Dict[str, List[Tuple[str, float]]] = {
        "identity": [],
        "performance": [],
        "schedule": [],
        "meta": [],
    }
    for res in report.resources:
        for f in res.fields:
            cat = _classify_field(f.field)
            category_fields[cat].append((f.field, f.coverage_ratio))
    out = [CategoryCoverage(category=k, fields=v) for k, v in category_fields.items()]
    # Stable ordering for deterministic tests / rendering
    order_index = {"identity": 0, "performance": 1, "schedule": 2, "meta": 3}
    out.sort(key=lambda c: order_index.get(c.category, 99))
    return out


class FieldCoverageRadarWidget(QWidget):  # pragma: no cover - paint logic visually exercised
    def __init__(self, categories: Iterable[CategoryCoverage], parent=None):
        super().__init__(parent)
        self._categories: List[CategoryCoverage] = list(categories)
        self.setMinimumSize(300, 220)
        self.setMouseTracking(True)

    # Data API ---------------------------------------------------------
    def set_categories(self, categories: Iterable[CategoryCoverage]) -> None:
        self._categories = list(categories)
        self.update()

    # Painting ---------------------------------------------------------
    def paintEvent(self, event):  # type: ignore[override]
        if not self._categories:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        w = self.width()
        h = self.height()
        center = QPointF(w / 2.0, h / 2.0 + 10)
        radius = min(w, h) * 0.35
        axes = len(self._categories)
        # Draw grid (5 concentric levels)
        levels = 5
        pen_grid = QPen(QColor(120, 120, 120, 120), 1)
        painter.setPen(pen_grid)
        for i in range(1, levels + 1):
            r = radius * (i / levels)
            painter.drawEllipse(center, r, r)
        # Axis lines + labels
        font_metrics = painter.fontMetrics()
        for idx, cat in enumerate(self._categories):
            angle = (360 / axes) * idx - 90  # start top
            rad = angle * 3.14159 / 180
            end_pt = QPointF(
                center.x() + radius * float(__import__("math").cos(rad)),
                center.y() + radius * float(__import__("math").sin(rad)),
            )
            painter.drawLine(center, end_pt)
            # Label
            text = (
                f"{cat.category}\n{cat.average_ratio:.0%}" if cat.fields else f"{cat.category}\n0%"
            )
            tw = font_metrics.horizontalAdvance(cat.category)
            painter.drawText(end_pt.x() - tw / 2, end_pt.y(), text)
        # Coverage polygon
        poly_points = []
        for idx, cat in enumerate(self._categories):
            ratio = cat.average_ratio
            angle = (360 / axes) * idx - 90
            rad = angle * 3.14159 / 180
            r = radius * ratio
            pt = QPointF(
                center.x() + r * float(__import__("math").cos(rad)),
                center.y() + r * float(__import__("math").sin(rad)),
            )
            poly_points.append(pt)
        painter.setPen(QPen(QColor(90, 170, 255, 200), 2))
        painter.setBrush(QBrush(QColor(90, 170, 255, 60)))
        for i in range(len(poly_points)):
            a = poly_points[i]
            b = poly_points[(i + 1) % len(poly_points)]
            painter.drawLine(a, b)
        # Fill (simple triangle fan)
        painter.setBrush(QBrush(QColor(90, 170, 255, 50)))
        painter.drawPolygon(*poly_points)  # type: ignore[arg-type]
        painter.end()

    # Interaction ------------------------------------------------------
    def mouseMoveEvent(self, event):  # type: ignore[override]
        if not self._categories:
            return
        # Determine closest axis by angle
        from math import atan2, degrees

        center_x = self.width() / 2.0
        center_y = self.height() / 2.0 + 10
        dx = event.position().x() - center_x
        dy = event.position().y() - center_y
        angle = degrees(atan2(dy, dx)) + 90
        if angle < 0:
            angle += 360
        axes = len(self._categories)
        axis_size = 360 / axes
        idx = int((angle + axis_size / 2) // axis_size) % axes
        if 0 <= idx < len(self._categories):
            QToolTip.showText(
                event.globalPosition().toPoint(), self._categories[idx].tooltip(), self
            )
