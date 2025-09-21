import json
from pathlib import Path
import pytest

from gui.services.custom_theme import load_custom_theme, CustomThemeError
from gui.services.theme_service import ThemeService
from gui.services.event_bus import EventBus, GUIEvent
from gui.services.service_locator import services


@pytest.fixture()
def temp_json(tmp_path: Path):
    def _write(data):
        p = tmp_path / "theme.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    return _write


def test_load_custom_theme_flatten(temp_json):
    p = temp_json({"color": {"background": {"primary": "#123456"}, "accent": {"base": "#ABC"}}})
    flat = load_custom_theme(p)
    assert flat["background.primary"] == "#123456"
    assert flat["accent.base"] == "#ABC"


def test_load_custom_theme_invalid_root(temp_json):
    p = temp_json([1, 2, 3])
    with pytest.raises(CustomThemeError):
        load_custom_theme(p)


def test_apply_custom_emits_event(temp_json):
    # Setup services
    bus = EventBus()
    services.register("event_bus", bus, allow_override=True)
    svc = ThemeService.create_default()
    services.register("theme_service", svc, allow_override=True)
    received = []
    bus.subscribe(GUIEvent.THEME_CHANGED, lambda evt: received.append(evt.payload))
    p = temp_json({"color": {"text": {"primary": "#222222"}}})
    flat = load_custom_theme(p)
    changed = svc.apply_custom(flat)
    assert changed == 1
    assert any("count" in r for r in received)
    assert svc.colors()["text.primary"] == "#222222"
