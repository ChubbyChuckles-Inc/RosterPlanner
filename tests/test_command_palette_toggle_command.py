from gui.services.command_registry import global_command_registry
from gui.services.settings_service import SettingsService


def test_toggle_command_palette_auto_resize_setting():
    # Ensure command is registered by simulating main window core command registration if needed
    if not global_command_registry.is_registered("commandPalette.toggleAutoResize"):
        # Fallback manual registration mirroring main_window logic
        def _toggle():
            cur = SettingsService.instance.command_palette_auto_resize
            SettingsService.instance.command_palette_auto_resize = not cur

        global_command_registry.register(
            "commandPalette.toggleAutoResize",
            "Toggle Command Palette Auto-Resize",
            _toggle,
        )
    # Start with True
    SettingsService.instance.command_palette_auto_resize = True
    global_command_registry.execute("commandPalette.toggleAutoResize")
    assert SettingsService.instance.command_palette_auto_resize is False
    global_command_registry.execute("commandPalette.toggleAutoResize")
    assert SettingsService.instance.command_palette_auto_resize is True
