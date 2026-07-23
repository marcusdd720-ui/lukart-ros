from core.configuration import Configuration


def test_set_and_get():
    config = Configuration()

    config.set("name", "KOS")

    assert config.get("name") == "KOS"


def test_default_value():
    config = Configuration()

    assert config.get("unknown", "default") == "default"


def test_has():
    config = Configuration()

    config.set("debug", True)

    assert config.has("debug")


def test_remove():
    config = Configuration()

    config.set("debug", True)
    config.remove("debug")

    assert not config.has("debug")


def test_clear():
    config = Configuration()

    config.set("a", 1)
    config.set("b", 2)

    config.clear()

    assert config.count() == 0


def test_count():
    config = Configuration()

    config.set("a", 1)
    config.set("b", 2)

    assert config.count() == 2


def test_keys():
    config = Configuration()

    config.set("b", 1)
    config.set("a", 2)

    assert config.keys() == ["a", "b"]


def test_as_dict():
    config = Configuration()

    config.set("name", "KOS")

    data = config.as_dict()

    assert data == {"name": "KOS"}