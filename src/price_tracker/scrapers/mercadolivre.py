"""Mercado Livre search scraper."""

from urllib.parse import quote

from price_tracker.models import Listing
from price_tracker.scrapers.base import clean_title, load_results, parse_brl, title_matches
from price_tracker.scrapers.browser import page

_SEARCH_URL = "https://lista.mercadolivre.com.br/"
_RESULTS_SELECTOR = "li.ui-search-layout__item, div.poly-card"
_EXTRACT = """
() => {
  const cards = [...document.querySelectorAll('li.ui-search-layout__item, div.poly-card')];
  const seen = new Set();
  const out = [];
  for (const el of cards) {
    const link = el.querySelector('a.poly-component__title, a.ui-search-link, h2 a, a');
    const titleNode = el.querySelector('.poly-component__title, .ui-search-item__title, h2');
    const fraction = el.querySelector('.andes-money-amount__fraction')?.textContent || '';
    const cents = el.querySelector('.andes-money-amount__cents')?.textContent || '';
    const title = (titleNode?.textContent || link?.textContent || '').trim();
    const url = link?.href || '';
    if (!title || !url || seen.has(url)) continue;
    seen.add(url);
    out.push({ title, url, price: fraction ? fraction + (cents ? ',' + cents : '') : '' });
  }
  return out;
}
"""


class MercadoLivreScraper:
    slug = "mercadolivre"

    def search(self, query: str, limit: int = 20) -> list[Listing]:
        url = _SEARCH_URL + quote("-".join(query.split()))
        with page() as tab:
            load_results(tab, url, _RESULTS_SELECTOR)
            cards = tab.evaluate(_EXTRACT)
        return [
            Listing(
                marketplace=self.slug,
                title=clean_title(card["title"]),
                url=card["url"],
                price_cents=parse_brl(card["price"]),
            )
            for card in cards[:limit]
        ]

    def variant_price(self, listing: Listing, targets: list[str]) -> int | None:
        # Mercado Livre lists each configuration (capacity + colour) as its own
        # single-price listing, with the attributes in the title — so the title
        # decides the match and the listing price is that config's price.
        return listing.price_cents if title_matches(listing, targets) else None
