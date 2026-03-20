"""
intent_service.py
Keyword-based intent detection with whole-word matching.
"""

import re
import logging
from typing import Optional
from app.services.faq_service import FAQService

logger = logging.getLogger(__name__)

INTERRUPT_PHRASES = ["hold on", "wait", "stop", "pause"]

FALLBACK_MESSAGE = (
    "I'm sorry, I can only help with Wise transfer related questions. "
    "This request needs a human support agent. "
    "Please hold while I transfer you. Goodbye."
)


def _matches(keyword: str, text: str) -> bool:
    """Whole-word match — 'ok' does NOT match inside 'book'."""
    pattern = r'(?<![a-z])' + re.escape(keyword.lower()) + r'(?![a-z])'
    return bool(re.search(pattern, text.lower()))


class IntentService:

    FAREWELL_FAQ_ID = "farewell"

    def __init__(self, faq_service: FAQService):
        self._faqs = faq_service.get_all()
        logger.info(f"IntentService ready with {len(self._faqs)} FAQs")

    def is_interrupt(self, text: str) -> bool:
        """Return True if text contains an interrupt phrase."""
        text_lower = text.lower().strip()
        return any(_matches(phrase, text_lower) for phrase in INTERRUPT_PHRASES)

    def is_farewell(self, text: str) -> bool:
        """Return True if the best matching FAQ is the farewell entry."""
        text_lower = text.lower()
        best_score = 0
        best_id = None

        for faq in self._faqs:
            keywords = faq.get("keywords", [])
            score = sum(1 for kw in keywords if _matches(kw, text_lower))
            if score > best_score:
                best_score = score
                best_id = faq.get("id")

        return best_id == self.FAREWELL_FAQ_ID and best_score > 0

    def get_response(self, text: str) -> str:
        """
        Find best-matching FAQ answer using whole-word keyword scoring.
        Returns FALLBACK_MESSAGE if no match found.
        """
        text_lower = text.lower()
        best_score = 0
        best_answer: Optional[str] = None

        for faq in self._faqs:
            keywords = faq.get("keywords", [])
            score = sum(1 for kw in keywords if _matches(kw, text_lower))

            if score > best_score:
                best_score = score
                best_answer = faq["answer"]

        if best_score > 0:
            logger.info(f"Intent matched with score={best_score}")
            return best_answer

        logger.info("No intent match - returning fallback")
        return FALLBACK_MESSAGE