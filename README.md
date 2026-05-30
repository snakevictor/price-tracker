# Price Tracker

Scrapes Brazilian marketplaces for a product and normalizes their listings.
Built incrementally — this first stage covers crawling, extraction, and
normalization only. Persistence, analytics (dbt), price-drop alerts, scheduling,
and the remaining marketplaces come in later stages.

Currently supported: Mercado Livre, Amazon.

## Stack

Python 3.12 (uv) · Playwright (Chromium).

## Setup

```bash
uv sync --extra dev
uv run playwright install chromium
```

## Usage

```bash
uv run price-tracker search "echo dot 5"
uv run price-tracker search "echo dot 5" --site amazon --limit 10
uv run price-tracker search "echo dot 5" --headed        # show the browser
```

Prints the normalized listings (title, price in BRL, URL) per marketplace. Sites
that serve an anti-bot wall are reported and skipped rather than aborting the run.

## Tests

```bash
uv run pytest        # normalization unit tests (no network)
uv run ruff check
```
