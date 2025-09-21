from gui.services.service_locator import ServiceLocator, services, ServiceNotFoundError
import pytest


class Dummy:
    def __init__(self, value: int) -> None:
        self.value = value


def test_get_typed_success():
    loc = ServiceLocator()
    loc.register("dummy", Dummy(5))
    obj = loc.get_typed("dummy", Dummy)
    assert isinstance(obj, Dummy) and obj.value == 5


def test_get_typed_type_mismatch():
    loc = ServiceLocator()
    loc.register("dummy", 123)
    with pytest.raises(TypeError):
        loc.get_typed("dummy", Dummy)


def test_override_context_basic():
    loc = ServiceLocator()
    loc.register("a", 1)
    assert loc.get("a") == 1
    with loc.override_context(a=2):
        assert loc.get("a") == 2
    assert loc.get("a") == 1  # restored


def test_override_context_ephemeral_service():
    loc = ServiceLocator()
    with loc.override_context(temp=10):
        assert loc.get("temp") == 10
    with pytest.raises(ServiceNotFoundError):
        loc.get("temp")


def test_override_context_nested():
    loc = ServiceLocator()
    loc.register("a", 1)
    with loc.override_context(a=2):
        assert loc.get("a") == 2
        with loc.override_context(a=3):
            assert loc.get("a") == 3
        # inner restored
        assert loc.get("a") == 2
    assert loc.get("a") == 1


def test_global_services_context_restore():
    services.register("shared", 42, allow_override=True)
    with services.override_context(shared=99):
        assert services.get("shared") == 99
    assert services.get("shared") == 42
