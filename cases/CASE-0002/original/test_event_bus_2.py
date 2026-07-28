from core.event_bus import EventBus


def test_subscribe():
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("test", handler)

    assert bus.has_subscribers("test")


def test_publish():
    bus = EventBus()

    result = []

    def handler(data):
        result.append(data)

    bus.subscribe("event", handler)

    bus.publish("event", 123)

    assert result == [123]


def test_unsubscribe():
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("event", handler)
    bus.unsubscribe("event", handler)

    assert not bus.has_subscribers("event")


def test_duplicate_subscribe():
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("event", handler)
    bus.subscribe("event", handler)

    assert bus.subscriber_count("event") == 1


def test_event_count():
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("a", handler)
    bus.subscribe("b", handler)

    assert bus.event_count() == 2


def test_clear():
    bus = EventBus()

    def handler(data):
        pass

    bus.subscribe("event", handler)

    bus.clear()

    assert bus.event_count() == 0
