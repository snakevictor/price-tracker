"""Amazon Brazil search scraper."""

from urllib.parse import quote_plus

from price_tracker.models import Listing
from price_tracker.scrapers.base import clean_title, load_results, parse_brl
from price_tracker.scrapers.browser import page

_SEARCH_URL = "https://www.amazon.com.br/s?k="
_RESULTS_SELECTOR = 'div[data-component-type="s-search-result"]'
_EXTRACT = """
() => {
  const cards = [...document.querySelectorAll('div[data-component-type="s-search-result"]')];
  return cards.map(el => {
    const link = el.querySelector('h2 a, a.a-link-normal.s-no-outline');
    const titleNode = el.querySelector('h2 span, h2');
    const price = el.querySelector('.a-price .a-offscreen')?.textContent || '';
    return {
      title: (titleNode?.textContent || '').trim(),
      url: link?.href || '',
      price,
    };
  }).filter(c => c.title && c.url);
}
"""


class AmazonScraper:
    slug = "amazon"

    def search(self, query: str, limit: int = 20) -> list[Listing]:
        url = _SEARCH_URL + quote_plus(query.strip())
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
