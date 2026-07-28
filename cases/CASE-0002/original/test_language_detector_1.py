from unittest.mock import patch

import pytest
from langdetect.lang_detect_exception import LangDetectException

from core.analysis.document import Document
from core.analysis.language_detector import LanguageDetector


@pytest.fixture
def detector():
    """
    Tworzy nową instancję LanguageDetector dla każdego testu.
    """
    return LanguageDetector()


def test_detect_polish(detector):
    doc = Document()
    doc.text = "To jest przykładowy polski tekst przeznaczony do testów."

    detector.handle(doc)

    assert doc.language == "pl"


def test_detect_english(detector):
    doc = Document()
    doc.text = "This is a simple English sentence used for language detection."

    detector.handle(doc)

    assert doc.language == "en"


def test_empty_text(detector):
    doc = Document()
    doc.text = ""

    detector.handle(doc)

    assert doc.language == "unknown"


def test_short_text(detector):
    doc = Document()
    doc.text = "abc"

    detector.handle(doc)

    assert doc.language == "unknown"


def test_supported_languages(detector):
    assert detector.is_supported("pl")
    assert detector.is_supported("en")
    assert detector.is_supported("de")


def test_not_supported_languages(detector):
    assert not detector.is_supported("ru")
    assert not detector.is_supported("jp")
    assert not detector.is_supported("xx")


def test_language_detector_exception(detector):
    """
    Jeżeli langdetect zgłosi wyjątek,
    LanguageDetector powinien zwrócić 'unknown'.
    """

    doc = Document()
    doc.text = "To jest tekst testowy."

    with patch(
        "core.analysis.language_detector.detect",
        side_effect=LangDetectException(
            0,
            "Test exception",
        ),
    ):
        detector.handle(doc)

    assert doc.language == "unknown"
