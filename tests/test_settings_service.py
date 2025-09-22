import importlib


def test_settings_service_defaults():
    from gui.services.settings_service import SettingsService

    settings = SettingsService.instance
    assert hasattr(settings, "allow_placeholders")
    assert settings.allow_placeholders is True


def test_settings_service_toggle():
    from gui.services.settings_service import SettingsService

    settings = SettingsService.instance
    settings.allow_placeholders = False
    assert settings.allow_placeholders is False
    # Reset back to True for other tests
    settings.allow_placeholders = True
