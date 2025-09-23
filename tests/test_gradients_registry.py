from gui.design import (
    list_gradients,
    get_gradient,
    register_gradient,
    GradientDef,
    GradientStop,
    clear_gradients,
)
import pytest


def test_default_gradients_present():
    ids = {g.id for g in list_gradients()}
    assert {"accent-ramp", "background-elevation", "status-positive-ramp"}.issubset(ids)


def test_register_invalid_gradient_errors():
    with pytest.raises(ValueError):
        register_gradient(
            GradientDef(id="bad", kind="linear", stops=(GradientStop(0.2, "#123456"),))
        )


def test_register_and_retrieve_custom_gradient():
    clear_gradients()
    register_gradient(
        GradientDef(
            id="custom",
            kind="linear",
            stops=(GradientStop(0.0, "#112233"), GradientStop(1.0, "#445566")),
        )
    )
    g = get_gradient("custom")
    assert g.stops[-1].color == "#445566"
