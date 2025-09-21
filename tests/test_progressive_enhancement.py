import pytest

from src.gui.design import progressive_enhancement as pe


def setup_function(_):
    # Start each test with an empty registry so tests control tier loading order.
    pe.clear_enhancement_registry()


def test_default_tiers_idempotent():
    first = pe.ensure_default_tiers()
    second = pe.ensure_default_tiers()
    assert first > 0  # defaults added on first call
    assert second == 0  # idempotent


def test_register_and_list_features():
    pe.ensure_default_tiers()
    pe.register_feature(
        pe.EnhancementFeature(
            id="hover-previews",
            tier_id="extended",
            description="Show miniature previews on hover",
            predicate=lambda ctx: True,
        )
    )
    pe.register_feature(
        pe.EnhancementFeature(
            id="gpu-transitions",
            tier_id="deluxe",
            description="High performance GPU transitions",
            predicate=lambda ctx: ctx and ctx.get("gpu") == "ok",
        )
    )
    feats = pe.list_features()
    assert [f.id for f in feats] == ["hover-previews", "gpu-transitions"]


def test_evaluate_active_features_context_sensitive():
    pe.ensure_default_tiers()
    pe.register_feature(
        pe.EnhancementFeature(
            id="anim",
            tier_id="extended",
            description="Animations",
            predicate=lambda ctx: ctx and ctx.get("allow_anim"),
        )
    )
    pe.register_feature(
        pe.EnhancementFeature(
            id="baseline-opt",
            tier_id="baseline",
            description="Always on baseline feature",
            predicate=lambda ctx: True,
        )
    )
    active_none = pe.evaluate_active_features({"allow_anim": False})
    assert [f.id for f in active_none] == ["baseline-opt"]
    active_yes = pe.evaluate_active_features({"allow_anim": True})
    assert {f.id for f in active_yes} == {"baseline-opt", "anim"}


def test_duplicate_tier_and_feature_errors():
    pe.ensure_default_tiers()
    with pytest.raises(ValueError):
        pe.register_tier(pe.EnhancementTier("baseline", "duplicate", 0))
    pe.register_feature(
        pe.EnhancementFeature(
            id="feat1",
            tier_id="extended",
            description="Desc 1",
            predicate=lambda ctx: True,
        )
    )
    with pytest.raises(ValueError):
        pe.register_feature(
            pe.EnhancementFeature(
                id="feat1",
                tier_id="extended",
                description="Desc duplicate",
                predicate=lambda ctx: True,
            )
        )


def test_unregistered_tier_for_feature():
    pe.ensure_default_tiers()
    with pytest.raises(ValueError):
        pe.register_feature(
            pe.EnhancementFeature(
                id="ghost",
                tier_id="missing",
                description="Should fail",
                predicate=lambda ctx: True,
            )
        )


def test_predicate_failure_fail_closed():
    pe.ensure_default_tiers()
    pe.register_feature(
        pe.EnhancementFeature(
            id="boom",
            tier_id="baseline",
            description="Raises",
            predicate=lambda ctx: (_ for _ in ()).throw(RuntimeError("x")),
        )
    )
    active = pe.evaluate_active_features({})
    assert active == []
