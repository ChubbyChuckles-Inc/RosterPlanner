from gui.app.bootstrap import create_app, parse_safe_mode


def test_parse_safe_mode():
    assert parse_safe_mode(["--safe-mode"]) is True
    assert parse_safe_mode(["--other"]) is False


def test_create_app_headless():
    ctx = create_app(headless=True, safe_mode=True)
    assert ctx.headless is True
    assert ctx.safe_mode is True
    assert ctx.design_tokens is not None
    assert ctx.services.get("design_tokens") is ctx.design_tokens


def test_create_app_idempotent_registration():
    c1 = create_app(headless=True)
    c2 = create_app(headless=True)
    # Should not raise; design_tokens service still present
    assert c1.services.get("design_tokens") is c2.services.get("design_tokens")
