"""Cheapest-matching-variant selection across a marketplace's candidates."""

from dataclasses import replace

from price_tracker.attributes import normalize
from price_tracker.models import Listing
from price_tracker.scrapers.base import MarketplaceScraper

# Model qualifiers that distinguish products; a listing carrying one the query
# didn't ask for is a different product (Pro vs Pro Max, 17 vs 17 Air).
_MODEL_QUALIFIERS = {"max", "plus", "ultra", "mini", "se", "lite", "pro", "air"}


def _relevant(title: str, query: str) -> bool:
    """Keep only listings for the same product: every query token present, and no
    extra model qualifier the query didn't ask for."""
    haystack = normalize(title)
    query_tokens = normalize(query).split()
    if not all(token in haystack for token in query_tokens):
        return False
    extra = (_MODEL_QUALIFIERS & set(haystack.split())) - set(query_tokens)
    return not extra


def best_match(
    scraper: MarketplaceScraper,
    query: str,
    targets: list[str],
    limit: int = 12,
    node: str | None = None,
    new_only: bool = True,
) -> Listing | None:
    """Cheapest listing that offers every target attribute, priced at that variant.

    Each candidate's real (post-selection) variant price is read from its detail
    page; the cheapest of those wins. Candidates are visited in ascending headline
    order so the search can stop once no remaining headline can beat the best found
    (a listing's chosen-variant price is never below its headline/base price).
    """
    candidates = sorted(
        scraper.search(query, limit=limit, node=node, new_only=new_only),
        key=lambda listing: (listing.price_cents is None, listing.price_cents or 0),
    )
    best: Listing | None = None
    for listing in candidates:
        if not _relevant(listing.title, query):
            continue
        if (
            best is not None
            and listing.price_cents is not None
            and listing.price_cents >= best.price_cents
        ):
            break
        price = scraper.variant_price(listing, targets)
        if price is not None and (best is None or price < best.price_cents):
            best = replace(listing, price_cents=price)
    return best
