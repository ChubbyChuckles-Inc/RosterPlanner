"""GUI components package.

Contains reusable UI widgets & supporting infrastructure. Presently exposes
only the internal component gallery registration API used for visual QA.

Stability:
 - Gallery API is internal (alpha); subject to change when component set expands.
 - Future public widgets will be documented individually with maturity levels.
"""

from __future__ import annotations

from .gallery import (
    register_demo,
    list_demos,
    get_demo,
    clear_demos,
    build_gallery_window,
)
from .progress_indicator import DeterminateProgress, IndeterminateProgress
from .schema_graph_widget import SchemaGraphWidget
from .row_detail_inspector import RowDetailInspector, RowDetailInspectorWidget
from .row_diff_viewer import RowDiffViewer, RowDiffViewerWidget
from .query_runner import QueryRunnerWidget
from .query_plan_analyzer import QueryPlanAnalyzerWidget
from .slow_query_log_viewer import SlowQueryLogViewer
from .index_usage_advisor import IndexUsageAdvisorWidget
from .maintenance_actions import MaintenanceActionsWidget

__all__ = [
    "register_demo",
    "list_demos",
    "get_demo",
    "clear_demos",
    "build_gallery_window",
    "DeterminateProgress",
    "IndeterminateProgress",
    "SchemaGraphWidget",
    "RowDetailInspector",
    "RowDetailInspectorWidget",
    "RowDiffViewer",
    "RowDiffViewerWidget",
    "QueryRunnerWidget",
    "QueryPlanAnalyzerWidget",
    "SlowQueryLogViewer",
    "IndexUsageAdvisorWidget",
    "MaintenanceActionsWidget",
]
