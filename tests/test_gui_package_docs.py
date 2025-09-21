"""Docstring presence and basic quality tests for GUI subpackages (Milestone 1.1.2)."""

import importlib
import inspect
import re

SUBPACKAGES = [
    "gui",
    "gui.app",
    "gui.components",
    "gui.components.gallery",
    "gui.services",
    "gui.testing",
    "gui.i18n",
    "gui.design",
]


def _quality(text: str) -> bool:
    # At least 2 non-empty lines and not just placeholder words
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if len(lines) < 2:
        return False
    placeholder_pattern = re.compile(r"^(todo|tbd|placeholder)$", re.IGNORECASE)
    return not all(placeholder_pattern.match(l) for l in lines)


def test_subpackage_docstrings_present_and_nontrivial():
    for name in SUBPACKAGES:
        module = importlib.import_module(name)
        doc = inspect.getdoc(module)
        assert doc, f"Missing docstring for {name}"
        assert _quality(doc), f"Docstring too trivial for {name}: {doc!r}"
