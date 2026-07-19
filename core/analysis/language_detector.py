from __future__ import annotations

import logging
from typing import Optional, Set

from langdetect import DetectorFactory, detect
from langdetect.lang_detect_exception import LangDetectException

from core.analysis.analysis_handler import AnalysisHandler
from core.plugin_manager import Plugin


# Powtarzalne wyniki testów
DetectorFactory.seed = 0


class LanguageDetector(AnalysisHandler, Plugin):
    """
    LanguageDetector

    Odpowiedzialność:
    - wykrywanie języka dokumentu,
    - integracja z Analysis Pipeline,
    - rejestracja jako Plugin.
    """

    __plugin__ = True

    DEFAULT_SUPPORTED = {
        "pl",
        "en",
        "de",
        "fr",
        "es",
    }

    FALLBACK_LANGUAGE = "unknown"
    OTHER_LANGUAGE = "other"

    def __init__(
        self,
        supported_languages: Optional[Set[str]] = None,
    ) -> None:
        super().__init__()

        self._logger = logging.getLogger(__name__)

        self._supported = (
            set(supported_languages)
            if supported_languages is not None
            else self.DEFAULT_SUPPORTED.copy()
        )

    def detect(self, text: str) -> str:
        """
        Wykrywa język tekstu.
        """

        if not text:
            self._logger.debug(
                "Language detection skipped: empty text."
            )
            return self.FALLBACK_LANGUAGE

        text = text.strip()

        if len(text) < 10:
            self._logger.debug(
                "Language detection skipped: text too short."
            )
            return self.FALLBACK_LANGUAGE

        try:

            language = detect(text)

            if language in self._supported:
                return language

            return self.OTHER_LANGUAGE

        except LangDetectException as exc:

            self._logger.debug(
                "Language detection failed: %s",
                exc,
            )

            return self.FALLBACK_LANGUAGE

        except Exception:

            self._logger.exception(
                "Unexpected language detection error."
            )

            return self.FALLBACK_LANGUAGE

    def handle(self, document):
        """
        Wykonuje analizę dokumentu.
        """

        text = getattr(document, "text", "")

        document.language = self.detect(text)

        return document

    def is_supported(
        self,
        language: str,
    ) -> bool:
        """
        Sprawdza czy język jest obsługiwany.
        """

        return language in self._supported