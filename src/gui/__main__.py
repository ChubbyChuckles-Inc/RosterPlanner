"""Module entrypoint for `python -m gui`.

Delegates to `gui.app.main` to launch the GUI application.
"""

from __future__ import annotations

from . import launcher as _launcher


def main():  # pragma: no cover - runtime delegation
    _launcher.main()


if __name__ == "__main__":  # pragma: no cover
    main()
