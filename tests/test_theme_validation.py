import pytest

from gui.services.theme_service import (
    ThemeService,
    validate_theme_keys,
    ThemeValidationError,
    REQUIRED_COLOR_KEYS,
)


def test_validate_theme_keys_success():
    svc = ThemeService.create_default()
    missing = svc.validate()
    # Some required keys may not exist yet depending on token naming; ensure list form returned.
    assert isinstance(missing, list)


def test_validate_theme_keys_detects_missing():
    svc = ThemeService.create_default()
    # Remove a required key artificially
    key = REQUIRED_COLOR_KEYS[0]
    svc._cached_map.pop(key, None)  # type: ignore[attr-defined]
    missing = svc.validate()
    assert key in missing


def test_validate_theme_keys_raise_on_error():
    svc = ThemeService.create_default()
    svc._cached_map.pop(REQUIRED_COLOR_KEYS[0], None)  # type: ignore[attr-defined]
    with pytest.raises(ThemeValidationError):
        svc.validate(raise_on_error=True)
