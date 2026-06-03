"""Command-line entry point."""

import argparse
import random
import time

from price_tracker.analysis import best_match
from price_tracker.attributes import parse_attr_args
from price_tracker.models import Listing
from price_tracker.scrapers import browser
from price_tracker.scrapers.amazon import AmazonScraper
from price_tracker.scrapers.base import ScraperBlocked
from price_tracker.scrapers.mercadolivre import MercadoLivreScraper

SCRAPERS = {
    "mercadolivre": MercadoLivreScraper,
    "amazon": AmazonScraper,
}


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
    mode = search.add_mutually_exclusive_group()
    mode.add_argument(
        "--headed", action="store_const", const="headed", dest="mode",
        help="Show the browser window (uses your display).",
    )
    mode.add_argument(
        "--headless", action="store_const", const="headless", dest="mode",
        help="Run headless (fast, but marketplaces may block it).",
    )
    search.set_defaults(mode="virtual")

    args = parser.parse_args(argv)
    if args.command == "search":
        _run_search(args)


def _run_search(args: argparse.Namespace) -> None:
    sites = [s.strip() for s in args.site.split(",") if s.strip()]
    unknown = [s for s in sites if s not in SCRAPERS]
    if unknown:
        raise SystemExit(f"Unknown site(s): {', '.join(unknown)}")

    targets = parse_attr_args(args.attr)
    browser.configure(mode=args.mode)
    try:
        if targets:
            _run_match(sites, args, targets)
        else:
            _run_list(sites, args)
    finally:
        browser.shutdown()


def _run_list(sites: list[str], args: argparse.Namespace) -> None:
    for index, site in enumerate(sites):
        if index:
            time.sleep(random.uniform(2, 5))
        try:
            listings = SCRAPERS[site]().search(args.query, limit=args.limit)
        except ScraperBlocked as exc:
            print(f"\n{site}: blocked — {exc}")
            continue
        print(f"\n{site}: {len(listings)} listing(s) for {args.query!r}")
        for listing in listings:
            _print_listing(listing)


def _run_match(sites: list[str], args: argparse.Namespace, targets: list[str]) -> None:
    print(f"matching {args.query!r} with attributes: {', '.join(targets)}")
    overall: Listing | None = None
    for index, site in enumerate(sites):
        if index:
            time.sleep(random.uniform(2, 5))
        try:
            match = best_match(SCRAPERS[site](), args.query, targets, limit=args.limit)
        except ScraperBlocked as exc:
            print(f"\n{site}: blocked — {exc}")
            continue
        if match is None:
            print(f"\n{site}: no matching listing")
            continue
        print(f"\n{site}: cheapest match for [{', '.join(targets)}]")
        _print_listing(match)
        if overall is None or (
            match.price_cents is not None and match.price_cents < overall.price_cents
        ):
            overall = match
    if overall is not None:
        print(f"\nglobal cheapest: {overall.marketplace} — R$ {overall.price:.2f}")
        print(f"  {overall.url}")


def _print_listing(listing: Listing) -> None:
    price = "—" if listing.price_cents is None else f"R$ {listing.price:.2f}"
    print(f"  {price:>14}  {listing.title[:70]}")
    print(f"  {'':>14}  {listing.url}")


if __name__ == "__main__":
    main()
