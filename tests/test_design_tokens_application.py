from gui.design.loader import load_tokens


def test_tokens_load_and_basic_qss_generation():
    tokens = load_tokens()
    qss = tokens.generate_qss()
    # Basic assertions: presence of at least one known color token comment and font size line
    assert "color.background.base" in qss or "color.background.base".replace("color.", "") in qss
    assert "font-size-base" in qss or "font-size-md" in qss


def test_no_hardcoded_hex_in_division_table_view(monkeypatch):
    # Read the file source and assert no raw hex colors outside token styling fallback lines
    import pathlib, re

    path = pathlib.Path("src/gui/views/division_table_view.py")
    source = path.read_text(encoding="utf-8")
    # Allow hex inside strings that are part of token fallback (we only introduced token-driven ones)
    hex_pattern = re.compile(r"#[0-9a-fA-F]{6}")
    matches = hex_pattern.findall(source)
    # We permit none now (all colors should come from tokens at runtime). If fallback left, relax assert accordingly.
    assert not matches, f"Unexpected hardcoded hex colors found: {matches}"
