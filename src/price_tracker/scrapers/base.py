"""Scraper interface and shared normalization helpers."""

import re
from typing import Protocol

from playwright.sync_api import Page
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from price_tracker.models import Listing


class ScraperBlocked(RuntimeError):
    """Raised when a marketplace serves an anti-bot wall instead of results."""


class MarketplaceScraper(Protocol):
    slug: str

    def search(self, query: str, limit: int = 20) -> list[Listing]: ...


def load_results(tab: Page, url: str, results_selector: str, timeout: int = 15000) -> None:
    """Navigate to a search URL and wait for results, detecting anti-bot walls."""
    tab.goto(url, wait_until="domcontentloaded", timeout=30000)
    if "captcha" in tab.url:
        raise ScraperBlocked(f"anti-bot wall: {tab.url}")
    try:
        tab.wait_for_selector(results_selector, timeout=timeout)
    except PlaywrightTimeoutError:
        raise ScraperBlocked(f"results did not load; landed on {tab.url}") from None


_NUMBER_RE = re.compile(r"[\d.,]+")


def parse_brl(text: str | None) -> int | None:
    """Parse a BRL price string ('R$ 1.234,56') into integer cents."""
    if not text:
        return None
    match = _NUMBER_RE.search(text)
    if not match:
        return None
    raw = match.group()
    if "," in raw:
        reais, _, cents = raw.rpartition(",")
        reais = reais.replace(".", "") or "0"
        cents = (cents + "00")[:2]
    else:
        reais, cents = raw.replace(".", ""), "00"
    if not reais.isdigit():
        return None
    return int(reais) * 100 + int(cents)


def clean_title(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "").strip()
