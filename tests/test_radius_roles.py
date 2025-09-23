from gui.design.radius_roles import get_radius, list_radius_roles, RADIUS_ROLE_MAP
from gui.design.loader import load_tokens, DesignTokens


def test_all_roles_return_int():
    tokens = load_tokens()
    for role in list_radius_roles():
        r = get_radius(role, tokens)
        assert isinstance(r, int)
        assert r >= 0


def test_monotonic_scale_ordering():
    tokens = load_tokens()
    base_keys = ["xs", "sm", "md", "lg", "xl"]
    raw = tokens.raw.get("radius", {})
    values = [raw[k] for k in base_keys]
    assert values == sorted(values), "Base radius scale should be ascending"


def test_pill_extreme():
    r = get_radius("pill")
    assert r >= 500


def test_missing_token_fallback(monkeypatch):
    tokens = load_tokens()
    # Remove 'lg' temporarily
    tokens.raw["radius"].pop("lg", None)
    # Role mapped to lg should fallback to default 4
    r_panel = get_radius("panel", tokens)
    assert r_panel == 4


def test_role_map_integrity():
    # Ensure declared map keys match list helper
    assert set(RADIUS_ROLE_MAP.keys()) == set(list_radius_roles())
