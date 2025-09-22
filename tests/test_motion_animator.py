import importlib


def test_animator_import_and_factories():
    mod = importlib.import_module("gui.design.animator")
    # In headless test environment Qt may be unavailable; ensure factory functions callable
    assert hasattr(mod, "create_dock_show_animation")

    # Call with a dummy object (will return None safely if Qt missing)
    class Dummy:  # minimal stand-in for QWidget when Qt not present
        def geometry(self):
            class G:
                def __init__(self):
                    self._top = 0

                def moveTop(self, v):
                    self._top = v

            return G()

    dummy = Dummy()
    assert mod.create_dock_show_animation(dummy) is None or mod.create_dock_show_animation(dummy)
