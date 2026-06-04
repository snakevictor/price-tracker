"""Command-line entry point."""

import argparse
import os
import random
import time

from price_tracker.analysis import best_match, relevant_listings
from price_tracker.attributes import normalize, parse_attr_args
from price_tracker.models import Listing
from price_tracker.scrapers import browser
from price_tracker.scrapers.amazon import AmazonScraper
from price_tracker.scrapers.base import MarketplaceScraper, ScraperBlocked
from price_tracker.scrapers.mercadolivre import MercadoLivreScraper

SCRAPERS = {
    "mercadolivre": MercadoLivreScraper,
    "amazon": AmazonScraper,
}

MODES = ("virtual", "headed", "headless")


def _default_mode() -> str:
    """Default browser mode, overridable via the PRICE_TRACKER_MODE env var."""
    mode = os.environ.get("PRICE_TRACKER_MODE", "virtual").strip().lower()
    return mode if mode in MODES else "virtual"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="price-tracker")
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="Search marketplaces for a query.")
    search.add_argument("query")
    search.add_argument(
        "--site",
        default=",".join(SCRAPERS),
        help="Comma-separated subset of: " + ", ".join(SCRAPERS),
    )
    search.add_argument("--limit", type=int, default=20)
    search.add_argument(
        "--attr", action="append", metavar="KEY=VALUE",
        help="Required attribute, e.g. --attr 256gb --attr cor=preto. Repeatable.",
    )
    search.add_argument(
        "--category", metavar="A>B>C",
        help="Pre-pick a category path (matched by name) to skip the prompt.",
    )
    search.add_argument(
        "--include-used", action="store_true",
        help="Include used/refurbished listings (default: new only).",
    )
    mode = search.add_mutually_exclusive_group()
    mode.add_argument(
        "--headed", action="store_const", const="headed", dest="mode",
        help="Show the browser window (uses your display).",
    )
    mode.add_argument(
        "--virtual", action="store_const", const="virtual", dest="mode",
        help="Invisible browser in a virtual display (default).",
    )
    mode.add_argument(
        "--headless", action="store_const", const="headless", dest="mode",
        help="Run headless (fast, but marketplaces may block it).",
    )
    search.set_defaults(mode=_default_mode())

    args = parser.parse_args(argv)
    if args.command == "search":
        _run_search(args)


def _run_search(args: argparse.Namespace) -> None:
    sites = [s.strip() for s in args.site.split(",") if s.strip()]
    unknown = [s for s in sites if s not in SCRAPERS]
    if unknown:
        raise SystemExit(f"Unknown site(s): {', '.join(unknown)}")

    targets = parse_attr_args(args.attr)
    new_only = not args.include_used
    browser.configure(mode=args.mode)
    if targets:
        suffix = "" if new_only else " (incl. used)"
        print(f"matching {args.query!r} with attributes: {', '.join(targets)}{suffix}")

    overall: Listing | None = None
    try:
        for index, site in enumerate(sites):
            if index:
                time.sleep(random.uniform(2, 5))
            scraper = SCRAPERS[site]()
            try:
                node = _resolve_node(scraper, args)
                if targets:
                    match = best_match(scraper, args.query, targets, node=node, new_only=new_only)
                    overall = _report_match(site, targets, match, overall)
                else:
                    listings = relevant_listings(
                        scraper, args.query, args.limit, node=node, new_only=new_only
                    )
                    print(f"\n{site}: {len(listings)} listing(s), cheapest first")
                    for listing in listings:
                        _print_listing(listing)
            except ScraperBlocked as exc:
                print(f"\n{site}: blocked — {exc}")
        if targets and overall is not None:
            print(f"\nglobal cheapest: {overall.marketplace} — R$ {overall.price:.2f}")
            print(f"  {overall.url}")
    finally:
        browser.shutdown()


def _resolve_node(scraper: MarketplaceScraper, args: argparse.Namespace) -> str | None:
    """Scope to a --category path if given; otherwise no scope. Drilling categories
    costs extra requests that trip Amazon's bot detection, and attribute matching
    already excludes accessories, so it stays opt-in."""
    return _resolve_path(scraper, args.query, args.category) if args.category else None


def _pick(options: list, name: str):
    """Best category option for a name: exact, then prefix, then substring."""
    target = normalize(name)
    for predicate in (
        lambda label: label == target,
        lambda label: label.startswith(target),
        lambda label: target in label,
    ):
        match = next((c for c in options if predicate(normalize(c.label))), None)
        if match is not None:
            return match
    return None


def _resolve_path(scraper: MarketplaceScraper, query: str, path: str) -> str | None:
    node = None
    for segment in (s.strip() for s in path.split(">") if s.strip()):
        match = _pick(scraper.category_options(query, node), segment)
        if match is None:
            break
        node = match.token
    return node


def _report_match(
    site: str, targets: list[str], match: Listing | None, overall: Listing | None
) -> Listing | None:
    if match is None:
        print(f"\n{site}: no matching listing")
        return overall
    print(f"\n{site}: cheapest match for [{', '.join(targets)}]")
    _print_listing(match)
    if overall is None or (
        match.price_cents is not None and match.price_cents < overall.price_cents
    ):
        return match
    return overall


def _print_listing(listing: Listing) -> None:
    price = "—" if listing.price_cents is None else f"R$ {listing.price:.2f}"
    print(f"  {price:>14}  {listing.title[:70]}")
    print(f"  {'':>14}  {listing.url}")


if __name__ == "__main__":
    main()
