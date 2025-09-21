from gui.design.onboarding_tour import (
    TourStep,
    TourDefinition,
    register_tour,
    get_tour,
    list_tours,
    clear_tours,
)
import pytest


def setup_function():
    clear_tours()


def test_register_and_retrieve_tour():
    steps = [
        TourStep(id="intro", title="Intro", body="Welcome"),
        TourStep(id="feature", title="Feature", body="Explain feature", next_id="finish"),
        TourStep(id="finish", title="Done", body="You're set"),
    ]
    tour = TourDefinition(id="onboarding_basic", steps=steps, description="Basic intro")
    register_tour(tour)

    fetched = get_tour("onboarding_basic")
    assert fetched.id == tour.id
    assert fetched.step_ids() == ["intro", "feature", "finish"]


def test_register_duplicate_tour_id():
    t = TourDefinition(id="dup", steps=[])
    register_tour(t)
    with pytest.raises(ValueError):
        register_tour(t)


def test_duplicate_step_id_rejected():
    steps = [TourStep(id="a", title="A", body="A"), TourStep(id="a", title="B", body="B")]
    tour = TourDefinition(id="bad", steps=steps)
    with pytest.raises(ValueError):
        register_tour(tour)


def test_list_tours_returns_all():
    register_tour(TourDefinition(id="t1", steps=[TourStep(id="s1", title="S1", body="B1")]))
    register_tour(TourDefinition(id="t2", steps=[TourStep(id="s2", title="S2", body="B2")]))
    ids = {t.id for t in list_tours()}
    assert ids == {"t1", "t2"}
