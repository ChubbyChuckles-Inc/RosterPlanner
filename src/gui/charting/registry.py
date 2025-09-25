"""Chart registry (Milestone 7.1)

Allows registering logical chart types decoupled from concrete backend.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, Any, List, Protocol, Optional, Tuple
from time import perf_counter
import hashlib
import json
from collections import OrderedDict

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
        self._snapshot_cache: "OrderedDict[str, Tuple[ChartResult, float]]" = OrderedDict()
        self._snapshot_cache_limit = 32  # simple LRU size

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
        """Eagerly build the requested chart and record build duration (ms)."""
        ct = self._types.get(req.chart_type)
        if ct is None:
            raise KeyError(f"Unknown chart type: {req.chart_type}")
        start = perf_counter()
        result = ct.builder(req, self._backend)
        elapsed = (perf_counter() - start) * 1000.0
        # Do not override if builder already set build_ms
        result.meta.setdefault("build_ms", elapsed)
        return result

    # ---------------- Lazy building -----------------------------------
    def build_lazy(self, req: ChartRequest) -> "LazyChartProxy":
        return LazyChartProxy(self, req)

    # ---------------- Snapshot caching (Milestone 7.10) ---------------
    def build_cached(self, req: ChartRequest) -> ChartResult:
        """Return chart using snapshot cache if identical request seen.

        Cache key derived from chart_type + JSON of data/options (stable sort keys).
        Stores the ChartResult; widget reuse is acceptable for static charts.
        """
        key_material = {
            "type": req.chart_type,
            "data": req.data,
            "options": req.options,
        }
        try:
            payload = json.dumps(key_material, sort_keys=True, default=str)
        except Exception:
            # Fallback: non-serializable data; bypass cache
            return self.build(req)
        key = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if key in self._snapshot_cache:
            result, _ts = self._snapshot_cache[key]
            # promote LRU
            self._snapshot_cache.move_to_end(key)
            # On a cache hit we explicitly mark (override) the flag so tests
            # can distinguish the initial build (False) from subsequent reuse (True).
            result.meta["cache_hit"] = True
            return result
        result = self.build(req)
        result.meta.setdefault("cache_hit", False)
        self._snapshot_cache[key] = (result, perf_counter())
        if len(self._snapshot_cache) > self._snapshot_cache_limit:
            self._snapshot_cache.popitem(last=False)  # evict LRU
        return result

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


class LazyChartProxy:
    """Proxy object deferring chart construction until first access.

    Access the `widget` property (or call materialize()) to trigger build.
    Subsequent accesses reuse the cached ChartResult.
    """

    __slots__ = ("_registry", "_req", "_result")

    def __init__(self, registry: ChartRegistry, req: ChartRequest) -> None:
        self._registry = registry
        self._req = req
        self._result: ChartResult | None = None

    def materialize(self) -> ChartResult:
        if self._result is None:
            self._result = self._registry.build(self._req)
            # annotate meta to indicate lazy
            self._result.meta.setdefault("lazy", True)
        return self._result

    @property
    def widget(self):  # noqa: D401
        return self.materialize().widget

    @property
    def meta(self) -> Dict[str, Any]:  # allow inspection even before build
        if self._result is None:
            return {"lazy": True, "built": False}
        return self._result.meta


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
