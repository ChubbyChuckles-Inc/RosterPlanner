import json, os, shutil
from pathlib import Path

from gui.app.config_store import AppConfig, save_config, load_config
from gui.services.service_locator import services
from gui.services.theme_service import ThemeService


def setup_function(func):
    # Isolate assets/themes directory in a temp folder under tests runtime cwd
    theme_dir = Path(os.getcwd()) / "assets" / "themes"
    if theme_dir.exists():
        shutil.rmtree(theme_dir)
    theme_dir.mkdir(parents=True, exist_ok=True)
    # Clear service locator state that could leak between tests
    for name in list(services._services.keys()):  # type: ignore[attr-defined]
        services._services.pop(name, None)  # type: ignore[attr-defined]


def test_filesystem_theme_persists_across_service_recreation(tmp_path):
    # 1. Create a fake exported custom theme file
    theme_dir = Path(os.getcwd()) / "assets" / "themes"
    custom = {
        "color": {
            "background": {"primary": "#112233", "secondary": "#223344"},
            "text": {"primary": "#FFFFFF"},
            "accent": {"base": "#FF5500"},
        }
    }
    with (theme_dir / "my_custom.json").open("w", encoding="utf-8") as fh:
        json.dump(custom, fh)

    # 2. Persist AppConfig referencing this custom theme variant
    cfg = AppConfig(theme_variant="my_custom")
    save_config(cfg)
    services.register("app_config", cfg, allow_override=True)

    # 3. Create ThemeService -> should pick up persisted variant + apply filesystem overlay
    svc = ThemeService.create_default()
    services.register("theme_service", svc, allow_override=True)

    assert svc.manager.variant == "my_custom"  # type: ignore[attr-defined]
    colors = svc.colors()
    # Ensure at least one of the custom colors present
    assert colors.get("background.primary") == "#112233"
    assert colors.get("accent.base") == "#FF5500"

    # 4. Simulate process restart: reload config & recreate service
    cfg2 = load_config()
    assert cfg2.theme_variant == "my_custom"
    # Clear existing service then recreate
    services._services.pop("theme_service", None)  # type: ignore[attr-defined]
    services.register("app_config", cfg2, allow_override=True)
    svc2 = ThemeService.create_default()
    assert svc2.manager.variant == "my_custom"  # type: ignore[attr-defined]
    colors2 = svc2.colors()
    assert colors2.get("background.primary") == "#112233"
    assert colors2.get("accent.base") == "#FF5500"
