"""Scraper interface and shared normalization helpers."""

import random
import re
import time
from dataclasses import dataclass
from typing import Protocol

from patchright.sync_api import Page
from patchright.sync_api import TimeoutError as PlaywrightTimeoutError

from price_tracker.attributes import normalize, option_matches
from price_tracker.models import Listing


class ScraperBlocked(RuntimeError):
    """Raised when a marketplace serves an anti-bot wall instead of results."""


@dataclass(frozen=True)
class Category:
    """A selectable category node; `token` is an opaque per-scraper handle."""

    label: str
    token: str


class MarketplaceScraper(Protocol):
    slug: str

    def category_options(self, query: str, node: str | None = None) -> list[Category]:
        """Categories to choose from at the current `node` (None = top level).
        Empty list means there is nothing further to narrow."""
        ...

    def search(
        self, query: str, limit: int = 20, node: str | None = None, new_only: bool = True
    ) -> list[Listing]: ...

    def variant_price(self, listing: Listing, targets: list[str]) -> int | None:
        """Price (cents) of the variant matching every target, or None if any target
        isn't available on this listing."""
        ...


def title_matches(listing: Listing, targets: list[str]) -> bool:
    """True if the listing title already satisfies every target attribute."""
    return all(option_matches(listing.title, t) for t in targets)


def link_href(tab: Page, text: str) -> str | None:
    """Href of the first <a> whose visible text equals `text` (normalized)."""
    return tab.evaluate(
        """(target) => {
            const norm = s => (s||'').normalize('NFKD').replace(/[\\u0300-\\u036f]/g,'')
              .replace(/\\s+/g,' ').trim().toLowerCase();
            const a = [...document.querySelectorAll('a')].find(e => norm(e.textContent) === target);
            return a ? a.href : null;
        }""",
        normalize(text),
    )


def load_results(tab: Page, url: str, results_selector: str, attempts: int = 3) -> None:
    """Open a search URL and wait for results, with human-like pacing, backoff
    retries, and anti-bot wall detection."""
    for attempt in range(attempts):
        tab.goto(url, wait_until="domcontentloaded", timeout=40000)
        _settle(tab)
        if "captcha" not in tab.url:
            try:
                tab.wait_for_selector(results_selector, timeout=15000)
                return
            except PlaywrightTimeoutError:
                pass
        if attempt + 1 < attempts:
            time.sleep(random.uniform(4, 9) * (attempt + 1))
    raise ScraperBlocked(f"anti-bot wall or no results after {attempts} tries: {tab.url}")


def _settle(tab: Page) -> None:
    """Brief human-like pause and scroll to trigger lazy loading."""
    tab.wait_for_timeout(random.uniform(700, 1800))
    tab.mouse.wheel(0, random.randint(600, 1400))
    tab.wait_for_timeout(random.uniform(500, 1200))


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
