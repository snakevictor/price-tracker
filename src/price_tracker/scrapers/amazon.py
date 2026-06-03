"""Amazon Brazil search scraper."""

from urllib.parse import quote_plus

from price_tracker.attributes import option_matches
from price_tracker.models import Listing
from price_tracker.scrapers.base import clean_title, load_results, parse_brl, title_matches
from price_tracker.scrapers.browser import page

_SEARCH_URL = "https://www.amazon.com.br/s?k="
_RESULTS_SELECTOR = 'div[data-component-type="s-search-result"]'

_DETAIL_SELECTOR = "#productTitle, #corePrice_feature_div"
_PRICE_JS = """
() => (document.querySelector(
  '#corePrice_feature_div .a-offscreen,'
  + ' #corePriceDisplay_desktop_feature_div .a-offscreen, .a-price .a-offscreen'
)?.textContent || '')
"""
_TITLE_JS = "() => (document.querySelector('#productTitle')?.textContent || '')"
# Click the twister option whose clean label matches a target (capacity/colour).
_CLICK_OPTION_JS = r"""
(target) => {
  const norm = s => (s || '')
    .normalize('NFKD').replace(/[̀-ͯ]/g, '')
    .toLowerCase().replace(/(\d+)\s*(gb|tb)\b/g, '$1$2').replace(/\s+/g, ' ').trim();
  const t = norm(target);
  const opts = [...document.querySelectorAll(
    '#twister li, [id^=inline-twister-row] li,'
    + ' #twister .a-button-text, [id^=inline-twister] .a-button-text'
  )];
  for (const o of opts) {
    const label = norm(o.getAttribute('title')
      || o.querySelector('.swatch-title-text, .a-button-text')?.textContent
      || o.textContent.split('/*')[0]);
    if (label === t || label.split(' ').includes(t)) {
      (o.querySelector('a, button, input') || o).click();
      return true;
    }
  }
  return false;
}
"""
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

    def variant_price(self, listing: Listing, targets: list[str]) -> int | None:
        # Colour is fixed per ASIN (in the title); capacity is a twister whose
        # default matches the title. If the title already covers every target the
        # headline price is correct; otherwise open the page and select the
        # missing options, reading the resulting price.
        if title_matches(listing, targets):
            return listing.price_cents
        with page() as tab:
            load_results(tab, listing.url, _DETAIL_SELECTOR)
            page_title = tab.evaluate(_TITLE_JS)
            for target in targets:
                if option_matches(page_title, target):
                    continue
                before = parse_brl(tab.evaluate(_PRICE_JS))
                if not tab.evaluate(_CLICK_OPTION_JS, target):
                    return None
                self._await_price_change(tab, before)
            return parse_brl(tab.evaluate(_PRICE_JS))

    def _await_price_change(self, tab, before: int | None, tries: int = 12) -> None:
        """Poll until the AJAX price settles to a new value after a swatch click."""
        for _ in range(tries):
            tab.wait_for_timeout(300)
            if parse_brl(tab.evaluate(_PRICE_JS)) != before:
                return
