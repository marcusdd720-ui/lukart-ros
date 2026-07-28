import pytest

from core.container import Container


class Service:
    pass


def test_register():
    container = Container()

    container.register("service", Service)

    assert container.has("service")


def test_resolve():
    container = Container()

    container.register("service", Service)

    service = container.resolve("service")

    assert isinstance(service, Service)


def test_singleton():
    container = Container()

    container.register("service", Service)

    s1 = container.resolve("service")
    s2 = container.resolve("service")

    assert s1 is s2


def test_unregister():
    container = Container()

    container.register("service", Service)

    container.unregister("service")

    assert not container.has("service")


def test_duplicate_registration():
    container = Container()

    container.register("service", Service)

    with pytest.raises(ValueError):
        container.register("service", Service)


def test_unknown_service():
    container = Container()

    with pytest.raises(KeyError):
        container.resolve("unknown")


def test_clear():
    container = Container()

    container.register("a", Service)
    container.register("b", Service)

    container.clear()

    assert container.count() == 0


def test_count():
    container = Container()

    container.register("a", Service)
    container.register("b", Service)

    assert container.count() == 2


def test_list():
    container = Container()

    container.register("b", Service)
    container.register("a", Service)

    assert container.list() == ["a", "b"]
