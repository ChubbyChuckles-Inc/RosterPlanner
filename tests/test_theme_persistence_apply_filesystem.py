import json, os, shutil
from pathlib import Path
from gui.services.service_locator import services
from gui.services.theme_service import ThemeService
from gui.app.config_store import AppConfig, load_config

def setup_function(func):
    # Reset services and assets
    for k in list(getattr(services, '_services', {}).keys()):  # type: ignore[attr-defined]
        services._services.pop(k, None)  # type: ignore[attr-defined]
    theme_dir = Path(os.getcwd()) / 'assets' / 'themes'
    if theme_dir.exists():
        shutil.rmtree(theme_dir)
    theme_dir.mkdir(parents=True, exist_ok=True)


def test_apply_filesystem_theme_persists_variant(tmp_path):
    # Create custom theme file 'ocean.json'
    theme_dir = Path(os.getcwd()) / 'assets' / 'themes'
    ocean = {
        'color': {
            'background': {'primary': '#002B36', 'secondary': '#073642'},
            'text': {'primary': '#FFFFFF'},
            'accent': {'base': '#268BD2'}
        }
    }
    with (theme_dir / 'ocean.json').open('w', encoding='utf-8') as fh:
        json.dump(ocean, fh)

    cfg = AppConfig()
    # Register config first so ThemeService picks it up
    services.register('app_config', cfg, allow_override=True)
    svc = ThemeService.create_default()
    services.register('theme_service', svc, allow_override=True)

    # Apply filesystem theme and ensure persistence
    assert svc.apply_filesystem_theme('ocean') is True
    assert svc.manager.variant == 'ocean'  # type: ignore[attr-defined]

    # Reload config from disk to confirm persistence
    cfg2 = load_config()
    assert cfg2.theme_variant == 'ocean'
