"""Chart registry (Milestone 7.1)

Allows registering logical chart types decoupled from concrete backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Protocol, Optional

from .types import ChartRequest, ChartResult
from .backends import MatplotlibChartBackend


@dataclass
class ChartType:
    """Metadata for a registered chart type."""

    chart_type: str
    builder: Callable[[ChartRequest, MatplotlibChartBackend], ChartResult]
    description: str
    plugin_id: Optional[str] = None
    plugin_version: Optional[str] = None
    meta: Dict[str, Any] | None = None


class ChartPluginProtocol(Protocol):  # pragma: no cover - structural only
    """Protocol for chart plugins.

    A plugin supplies an id, version, and a register() callback to
    contribute one or more chart types via the provided registrar.
    """

    id: str
    version: str

    def register(self, registrar: "ChartRegistrar") -> None:  # noqa: D401
        ...


class ChartRegistrar:
    """Helper passed to plugins for registering chart types safely."""

    def __init__(self, registry: "ChartRegistry", plugin_id: str, version: str) -> None:
        self._registry = registry
        self._plugin_id = plugin_id
        self._version = version

    def register(
        self,
        chart_type: str,
        builder: Callable[[ChartRequest, MatplotlibChartBackend], ChartResult],
        description: str,
        **meta: Any,
    ) -> None:
        self._registry.register(
            chart_type,
            builder,
            description,
            plugin_id=self._plugin_id,
            plugin_version=self._version,
            meta=meta or None,
        )


class ChartRegistry:
    def __init__(self) -> None:
        self._types: Dict[str, ChartType] = {}
        self._backend = MatplotlibChartBackend()
        self._plugins: Dict[str, str] = {}  # plugin_id -> version

    # ---------------- Core type registration ----------------------------
    def register(
        self,
        chart_type: str,
        builder,
        description: str,
        *,
        plugin_id: str | None = None,
        plugin_version: str | None = None,
        meta: Dict[str, Any] | None = None,
    ) -> None:
        if chart_type in self._types:
            raise ValueError(f"Chart type already registered: {chart_type}")
        self._types[chart_type] = ChartType(
            chart_type,
            builder,
            description,
            plugin_id=plugin_id,
            plugin_version=plugin_version,
            meta=meta,
        )

    def build(self, req: ChartRequest) -> ChartResult:
        ct = self._types.get(req.chart_type)
        if ct is None:
            raise KeyError(f"Unknown chart type: {req.chart_type}")
        return ct.builder(req, self._backend)

    def list_types(self) -> Dict[str, str]:
        return {k: v.description for k, v in self._types.items()}

    def list_types_by_plugin(self, plugin_id: str) -> Dict[str, str]:
        return {k: v.description for k, v in self._types.items() if v.plugin_id == plugin_id}

    # ---------------- Plugin management --------------------------------
    def register_plugin(self, plugin: ChartPluginProtocol) -> None:
        if plugin.id in self._plugins:
            raise ValueError(f"Plugin already registered: {plugin.id}")
        registrar = ChartRegistrar(self, plugin.id, plugin.version)
        plugin.register(registrar)
        # Only mark plugin registered after successful register() to avoid partial state
        self._plugins[plugin.id] = plugin.version

    def list_plugins(self) -> Dict[str, str]:
        return dict(self._plugins)


chart_registry = ChartRegistry()


def register_chart_type(chart_type: str, builder, description: str) -> None:
    """Backward-compatible helper for core (non-plugin) charts."""
    chart_registry.register(chart_type, builder, description)


def register_chart_plugin(plugin: ChartPluginProtocol) -> None:
    """Register a chart plugin implementing ChartPluginProtocol."""
    chart_registry.register_plugin(plugin)


# ---------------- Built-in basic line chart -----------------------------


def _basic_line_builder(req: ChartRequest, backend: MatplotlibChartBackend) -> ChartResult:
    data = req.data
    if not isinstance(data, dict):
        raise TypeError("Basic line chart expects dict with 'series' key")
    series = data.get("series")
    if not series:
        raise ValueError("No series provided")
    labels = data.get("labels")
    x_values = data.get("x")
    widget = backend.create_line_chart(
        series, labels=labels, title=(req.options or {}).get("title"), x_values=x_values
    )
    return ChartResult(widget=widget, meta={"series_count": len(series)})


register_chart_type("line.basic", _basic_line_builder, "Basic multi-series line chart")
