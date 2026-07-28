import pytest

from core.registry import Registry


def test_register_service():
    registry = Registry()

    obj = object()

    registry.register("service", obj)

    assert registry.has("service")


def test_get_service():
    registry = Registry()

    obj = object()

    registry.register("service", obj)

    assert registry.get("service") is obj


def test_unregister():
    registry = Registry()

    obj = object()

    registry.register("service", obj)
    registry.unregister("service")

    assert not registry.has("service")


def test_duplicate_registration():
    registry = Registry()

    registry.register("service", object())

    with pytest.raises(ValueError):
        registry.register("service", object())


def test_unknown_service():
    registry = Registry()

    with pytest.raises(KeyError):
        registry.get("unknown")


def test_clear():
    registry = Registry()

    registry.register("a", object())
    registry.register("b", object())

    registry.clear()

    assert registry.count() == 0


def test_count():
    registry = Registry()

    registry.register("a", object())
    registry.register("b", object())

    assert registry.count() == 2


def test_list():
    registry = Registry()

    registry.register("b", object())
    registry.register("a", object())

    assert registry.list() == ["a", "b"]
