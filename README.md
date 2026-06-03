# Price Tracker

Scrapes Brazilian marketplaces for a product and normalizes their listings.
Built incrementally — this first stage covers crawling, extraction, and
normalization only. Persistence, analytics (dbt), price-drop alerts, scheduling,
and the remaining marketplaces come in later stages.

Currently supported: Mercado Livre, Amazon.

## Stack

Python 3.12 (uv) · Patchright (undetected Playwright) + Chromium · Xvfb.

## Setup

```bash
uv sync --extra dev
uv run patchright install chromium
sudo pacman -S xorg-server-xvfb     # Arch; any distro's Xvfb package works
```

## Usage

```bash
uv run price-tracker search "echo dot 5"                 # default: invisible browser
uv run price-tracker search "echo dot 5" --site amazon --limit 10
uv run price-tracker search "echo dot 5" --headed        # show the browser window
uv run price-tracker search "echo dot 5" --headless      # fast, but often blocked
```

Prints the normalized listings (title, price in BRL, URL) per marketplace. Sites
that serve an anti-bot wall are reported and skipped rather than aborting the run.

### Anti-bot resilience

Marketplaces block headless browsers, so by default the scraper runs a real
Chromium inside a virtual display (Xvfb) — undetectable like a headed browser but
with no window, and fine for unattended/cloud runs. It uses Patchright (which
fixes the `Runtime.enable` CDP leak), a persistent profile (`.browser-profile/`),
and human-like pacing with backoff. If a site challenges you, run once with
`--headed` to solve it; the persistent profile remembers it.

## Tests

```bash
uv run pytest        # normalization unit tests (no network)
uv run ruff check
```
