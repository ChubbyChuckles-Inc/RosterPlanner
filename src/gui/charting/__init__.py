"""Charting abstraction layer (Milestone 7.1)

Provides a thin wrapper API that hides the concrete plotting backend
so higher level view models / views can request charts without
coupling to matplotlib or PyQtGraph directly.

Initial backend choice: matplotlib with its QtAgg backend, because
it is already a dependency (present in pyproject) and sufficient for
static + moderately interactive plots (pan/zoom, tooltips later).

Future extension: add a PyQtGraph backend implementation for higher
performance real-time scenarios; both must conform to ChartBackendProtocol.
"""

from .backends import MatplotlibChartBackend  # noqa: F401
from .registry import chart_registry, register_chart_type  # noqa: F401
from .types import ChartRequest, ChartResult  # noqa: F401
from . import player_charts  # noqa: F401  # registers player chart types
from . import team_charts  # noqa: F401  # registers team chart types (availability heatmap)
from . import division_charts  # noqa: F401  # registers division standings evolution chart
from . import match_charts  # noqa: F401  # registers match volume & win % chart
