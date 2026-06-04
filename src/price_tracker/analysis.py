"""Cheapest-matching-variant selection across a marketplace's candidates."""

from dataclasses import replace

from price_tracker.attributes import is_relevant
from price_tracker.models import Listing
from price_tracker.scrapers.base import MarketplaceScraper


def relevant_listings(
    scraper: MarketplaceScraper,
    query: str,
    count: int,
    node: str | None = None,
    new_only: bool = True,
    max_pages: int = 6,
) -> list[Listing]:
    """The `count` cheapest listings that actually name the queried product, walking
    the price-ascending pages and skipping different products (and accessories,
    excluded by the category node)."""
    found: list[Listing] = []
    for page_num in range(1, max_pages + 1):
        candidates = scraper.search(
            query, limit=100, node=node, new_only=new_only, page_num=page_num
        )
        if not candidates:
            break
        found.extend(c for c in candidates if is_relevant(c.title, query))
        if len(found) >= count:
            break
    return sorted(found, key=lambda x: (x.price_cents is None, x.price_cents or 0))[:count]


def best_match(
    scraper: MarketplaceScraper,
    query: str,
    targets: list[str],
    limit: int = 100,
    node: str | None = None,
    new_only: bool = True,
    max_pages: int = 6,
) -> Listing | None:
    """Cheapest listing that offers every target attribute, priced at that variant.

    Walks the marketplace's price-ascending results, analyzing each title: listings
    that name a different product (or fail the attributes) are skipped, and the
    search pages deeper until the matches surface. Because results are globally
    price-ascending, once a candidate's headline price is at or above the best match
    found, nothing cheaper remains and the walk stops.
    """
    best: Listing | None = None
    for page_num in range(1, max_pages + 1):
        candidates = scraper.search(
            query, limit=limit, node=node, new_only=new_only, page_num=page_num
        )
        if not candidates:
            break
        for listing in sorted(
            candidates, key=lambda x: (x.price_cents is None, x.price_cents or 0)
        ):
            if (
                best is not None
                and listing.price_cents is not None
                and listing.price_cents >= best.price_cents
            ):
                return best
            if not is_relevant(listing.title, query):
                continue
            price = scraper.variant_price(listing, targets)
            if price is not None and (best is None or price < best.price_cents):
                best = replace(listing, price_cents=price)
    return best
