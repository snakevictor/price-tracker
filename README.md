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
uv run price-tracker search "echo dot 5"                 # list normalized results
uv run price-tracker search "echo dot 5" --site amazon --limit 10
uv run price-tracker search "echo dot 5" --headed        # watch it in a real window
uv run price-tracker search "echo dot 5" --headless      # fast, but often blocked

# make a visible window the default for a session of manual test runs
export PRICE_TRACKER_MODE=headed
uv run price-tracker search "echo dot 5"                 # now opens a window
uv run price-tracker search "echo dot 5" --virtual       # ...override back per-run

# match attributes and return the cheapest listing that offers that exact config
uv run price-tracker search "iphone 17 pro" --attr 256gb --attr cor=prata

# optionally scope to a category path; include used units
uv run price-tracker search "iphone 17 pro" --attr 256gb \
  --category "Eletrônicos>Celulares e Comunicação>Celulares e Smartphones"
uv run price-tracker search "iphone 17 pro" --include-used
```

Without `--attr` it lists the relevant listings cheapest-first. With `--attr`
(repeatable, `key=value` or bare `value`) it returns the cheapest listing per
marketplace that actually offers every requested attribute, priced at that variant,
plus the global cheapest. Anti-bot walls are reported and the site skipped.

### Category, condition, and sorting

Only **new** listings are returned by default via each platform's own condition
filter (`--include-used` to keep used/refurbished). `--category "A>B>C"` optionally
narrows to a marketplace category, matched by name down the tree; it's opt-in
because drilling Amazon's category tree costs extra requests that trip its bot
detection, and with `--attr` it isn't needed (attribute matching already drops
accessories). Sorting is cheapest-first: Mercado Livre's own price sort keeps query
relevance, but Amazon's does not (it ranks the whole category by price and buries
the product), so for Amazon we keep relevance — which front-loads the queried
product — and rank the matches by price in code.

### Attribute matching

Values are normalized (accents, units, synonyms) so `256gb`≈`256 GB` and
`prata`/`silver`≈`Prateado`. A listing is ranked by the price of its **matching
variant**: Mercado Livre lists each configuration separately (matched from the
title), while Amazon's capacity is a picker — when the wanted size isn't the
default the page is opened and the variant selected before reading its price.
Listings for a different product (e.g. Pro Max when you asked for Pro) are excluded.

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
