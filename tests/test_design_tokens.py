import pytest
from gui.design import load_tokens, DesignTokens, TokenValidationError
from pathlib import Path
import json


def test_load_tokens_default():
    tokens = load_tokens()
    assert isinstance(tokens, DesignTokens)
    # Basic spot checks
    assert tokens.color('background', 'base').startswith('#')
    assert tokens.font_size('base') > 0


def test_spacing_and_font_size():
    tokens = load_tokens()
    assert tokens.spacing('3') == 8
    assert tokens.font_size('lg') == 18


def test_missing_file(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_tokens(tmp_path / 'nope.json')


def test_validation_error(tmp_path: Path):
    bad = {"spacing": {}, "typography": {"scale": {}}, "color": {}}
    p = tmp_path / 'tokens.json'
    p.write_text(json.dumps(bad), encoding='utf-8')
    from gui.design.loader import _validate_tokens  # type: ignore
    with pytest.raises(TokenValidationError):
        _validate_tokens(bad)


def test_generate_qss():
    tokens = load_tokens()
    qss = tokens.generate_qss()
    assert 'AUTO-GENERATED' in qss
    assert 'color.background.base' in qss
