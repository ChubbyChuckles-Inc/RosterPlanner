import pytest
from gui.services.service_locator import (
    services,
    ServiceAlreadyRegisteredError,
    ServiceNotFoundError,
    ServiceLocator,
)


def setup_function(_):
    services.clear()


def test_register_and_get():
    services.register("config", {"env": "test"})
    assert services.get("config")["env"] == "test"


def test_double_register_raises():
    services.register("x", 1)
    with pytest.raises(ServiceAlreadyRegisteredError):
        services.register("x", 2)


def test_override():
    services.register("cache", {"size": 10})
    services.override("cache", {"size": 20})
    assert services.get("cache")["size"] == 20


def test_try_get_default():
    assert services.try_get("missing", 123) == 123


def test_unregister():
    services.register("temp", object())
    services.unregister("temp")
    with pytest.raises(ServiceNotFoundError):
        services.get("temp")


def test_list_keys():
    services.register("a", 1)
    services.register("b", 2)
    assert set(services.list_keys()) == {"a", "b"}


def test_local_instance_isolated():
    local = ServiceLocator()
    local.register("foo", 1)
    assert local.get("foo") == 1
    with pytest.raises(ServiceNotFoundError):
        services.get("foo")
