import types
from gui.services import theme_service as theme_mod
from gui.services.theme_service import ThemeService, STYLE_RECALC_WARN_THRESHOLD_MS
from gui.services.service_locator import services
from gui.services.event_bus import EventBus


class FakeThemeManager:
    def __init__(self):
        self._variant = "default"
        self._accent = "#3366FF"
        self._map = {
            "background.base": "#101010",
            "background.elevated": "#181818",
            "surface.primary": "#202020",
            "text.primary": "#FFFFFF",
            "text.muted": "#BBBBBB",
            "accent.primary": self._accent,
        }

    def active_map(self):
        return self._map.items()

    def set_variant(self, v):  # returns a ThemeDiff-like object
        old = self._variant
        self._variant = v
        changed = {}
        if v != old:
            changed["_variant"] = (old, v)
        return types.SimpleNamespace(changed=changed, no_changes=not changed)

    def set_accent_base(self, hex_color):
        old = self._accent
        self._accent = hex_color
        self._map["accent.primary"] = hex_color
        changed = {}
        if old != hex_color:
            changed["accent.primary"] = (old, hex_color)
        return types.SimpleNamespace(changed=changed, no_changes=not changed)


def test_style_recalc_instrumentation_slow_event(monkeypatch):
    # Register event bus
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)

    # Force a slow elapsed time by patching perf_counter sequence
    calls = []

    def fake_perf():
        calls.append(len(calls))
        # First call returns 0.0, second returns threshold in seconds + small delta
        if len(calls) == 1:
            return 0.0
        return (STYLE_RECALC_WARN_THRESHOLD_MS + 5) / 1000.0

    monkeypatch.setattr(theme_mod, "perf_counter", fake_perf)

    mgr = FakeThemeManager()
    svc = ThemeService(manager=mgr, _cached_map=dict(mgr.active_map()))

    events = {}

    def handler(evt):
        events.setdefault(evt.name, []).append(evt.payload)

    bus.subscribe("style_recalc_slow", handler)
    svc.set_variant("brand-neutral")

    assert "style_recalc_slow" in events, "Expected slow style recalc event emission"
    payload = events["style_recalc_slow"][0]
    assert payload["kind"] == "variant"
    assert payload["elapsed_ms"] >= STYLE_RECALC_WARN_THRESHOLD_MS


def test_style_recalc_instrumentation_fast_no_event(monkeypatch):
    bus = services.try_get("event_bus") or EventBus()
    services.register("event_bus", bus, allow_override=True)

    def fake_perf():
        # Always return 0 => elapsed 0
        return 0.0

    monkeypatch.setattr(theme_mod, "perf_counter", fake_perf)
    mgr = FakeThemeManager()
    svc = ThemeService(manager=mgr, _cached_map=dict(mgr.active_map()))

    captured = []

    def handler(evt):
        captured.append(evt)

    bus.subscribe("style_recalc_slow", handler)
    svc.set_accent("#FF0000")
    assert not captured, "Fast recalculation should not emit slow event"
