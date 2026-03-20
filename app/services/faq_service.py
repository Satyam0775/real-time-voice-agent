"""
faq_service.py
Loads FAQ entries from the JSON knowledge base.
"""

import json
import logging
import os
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


class FAQService:
    """Loads and provides access to the FAQ knowledge base."""

    def __init__(self, faq_path: str = None):
        if faq_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            faq_path = os.path.join(base_dir, "data", "faq.json")

        self._faqs: List[Dict[str, Any]] = []
        self._load(faq_path)

    def _load(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                self._faqs = json.load(f)
            logger.info(f"Loaded {len(self._faqs)} FAQ entries from {path}")
        except FileNotFoundError:
            logger.error(f"FAQ file not found: {path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid FAQ JSON: {e}")
            raise

    def get_all(self) -> List[Dict[str, Any]]:
        """Return all FAQ entries."""
        return self._faqs
