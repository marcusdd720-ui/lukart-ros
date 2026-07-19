from core.analysis.chain import AnalysisHandler


class AddOneHandler(AnalysisHandler):

    def handle(self, value):
        return value + 1


class MultiplyHandler(AnalysisHandler):

    def handle(self, value):
        return value * 2


def test_single_handler():

    handler = AddOneHandler()

    assert handler.execute(5) == 6


def test_chain():

    first = AddOneHandler()
    second = MultiplyHandler()

    first.set_next(second)

    assert first.execute(5) == 12


def test_set_next_returns_handler():

    first = AddOneHandler()
    second = MultiplyHandler()

    returned = first.set_next(second)

    assert returned is second