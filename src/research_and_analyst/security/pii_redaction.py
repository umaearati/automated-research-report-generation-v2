"""
PII redaction using Microsoft Presidio.

Applied to:
  - the research topic string supplied by the caller (before it enters any prompt)
  - Tavily search result content (before it's added to interview context)
  - the final interview transcript (before it's persisted / passed to the writer)

This keeps PII that shows up in web search results (names, emails, phone
numbers, etc. embedded in scraped page content) from being echoed back
verbatim into the generated report or logs.

Presidio's NLP engine (spaCy) is expensive to load, so the analyzer/anonymizer
pair is built once and reused via `get_redactor()`.
"""

import logging
from typing import Optional

log = logging.getLogger(__name__)

# Entity types we actively redact. DATE_TIME and URL are excluded — dates and
# links are usually necessary for the report to make sense and are not PII
# on their own.
DEFAULT_ENTITIES = [
    "PERSON",
    "EMAIL_ADDRESS",
    "PHONE_NUMBER",
    "CREDIT_CARD",
    "US_SSN",
    "UK_NHS",
    "IBAN_CODE",
    "IP_ADDRESS",
    "LOCATION",
    "CRYPTO",
]

_redactor_instance: Optional["PIIRedactor"] = None


class PIIRedactor:
    """Wraps a Presidio AnalyzerEngine + AnonymizerEngine pair."""

    def __init__(self, entities: Optional[list] = None, language: str = "en"):
        self.entities = entities or DEFAULT_ENTITIES
        self.language = language
        self._available = False

        try:
            from presidio_analyzer import AnalyzerEngine
            from presidio_anonymizer import AnonymizerEngine

            self.analyzer = AnalyzerEngine()
            self.anonymizer = AnonymizerEngine()
            self._available = True
            log.info("Presidio PII redactor initialised | entities=%s", self.entities)
        except ImportError:
            log.warning(
                "presidio-analyzer / presidio-anonymizer not installed — "
                "PII redaction is disabled. Run `pip install presidio-analyzer presidio-anonymizer` "
                "and `python -m spacy download en_core_web_lg`."
            )
        except Exception as e:
            log.error("Failed to initialise Presidio engines | error=%s", str(e), exc_info=True)

    @property
    def available(self) -> bool:
        return self._available

    def redact(self, text: str) -> tuple[str, int]:
        """
        Redact PII from `text`.

        Returns:
            (redacted_text, entity_count) — entity_count is the number of
            PII spans found, so callers can log redaction volume without
            logging the PII itself.
        """
        if not text or not self._available:
            return text, 0

        try:
            results = self.analyzer.analyze(
                text=text, entities=self.entities, language=self.language
            )
            if not results:
                return text, 0

            anonymized = self.anonymizer.anonymize(text=text, analyzer_results=results)
            return anonymized.text, len(results)
        except Exception as e:
            log.error("PII redaction failed, returning original text | error=%s", str(e), exc_info=True)
            return text, 0

    def redact_search_documents(self, documents: list) -> tuple[list, int]:
        """
        Redact PII from a list of Tavily-style search result dicts
        ({"url": ..., "content": ...}), preserving structure.

        Tavily's tool occasionally returns plain strings instead of dicts
        (e.g. for certain error/edge-case responses), so each entry is
        normalised defensively rather than assumed to be a dict.
        """
        if not self._available:
            return documents, 0

        total_hits = 0
        redacted_docs = []
        for doc in documents:
            if isinstance(doc, dict):
                content = doc.get("content", "")
                redacted_content, hits = self.redact(content)
                total_hits += hits
                redacted_docs.append({**doc, "content": redacted_content})
            elif isinstance(doc, str):
                redacted_content, hits = self.redact(doc)
                total_hits += hits
                redacted_docs.append({"url": "#", "content": redacted_content})
            else:
                log.warning("Unexpected search result type, skipping redaction | type=%s", type(doc).__name__)
                redacted_docs.append(doc)

        return redacted_docs, total_hits


def get_redactor() -> PIIRedactor:
    """Return the process-wide PIIRedactor singleton, creating it on first use."""
    global _redactor_instance
    if _redactor_instance is None:
        _redactor_instance = PIIRedactor()
    return _redactor_instance
