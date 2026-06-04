"""Amazon Brazil search scraper."""

from urllib.parse import parse_qs, quote_plus, urlencode, urlparse, urlunparse

from price_tracker.attributes import option_matches
from price_tracker.models import Listing
from price_tracker.scrapers.base import (
    Category,
    clean_title,
    load_results,
    parse_brl,
    title_matches,
)
from price_tracker.scrapers.browser import page

_SEARCH_URL = "https://www.amazon.com.br/s?k="
_RESULTS_SELECTOR = 'div[data-component-type="s-search-result"]'

# Top-level departments from the search-bar dropdown (level-1 categories).
_DEPARTMENTS_JS = """
() => [...document.querySelectorAll('#searchDropdownBox option, #nav-search-dropdown option')]
  .map(o => ({label:(o.textContent||'').trim(), alias:(o.value||'').replace('search-alias=','')}))
  .filter(o => o.label && o.alias && o.alias !== 'aps')
"""
# In-page "Departamento" refinement links carry a second browse node (…,n:NNN).
_CATEGORY_LINKS_JS = r"""
() => [...document.querySelectorAll('#s-refinements a')]
  .map(a => ({
    label: (a.textContent || '').replace(/\s+/g, ' ').trim(),
    href: a.getAttribute('href') || '',
  }))
  .filter(x => x.label && /(%2Cn%3A|,n:)\d+/.test(x.href) && !/qualquer/i.test(x.label))
"""

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


# Amazon BR "Novo" condition filter value (a stable platform constant, like the
# sort key — not a keyword list). Merged into rh so it survives pagination.
_NOVO_CONDITION = "p_n_condition-type:13862762011"


def _node_token(href: str) -> str:
    """Keep only the department (i) and browse-node (rh) params from a refinement href."""
    q = parse_qs(urlparse(href).query)
    return urlencode({k: q[k][0] for k in ("i", "rh") if k in q})


def _node_url(query: str, node: str | None) -> str:
    url = _SEARCH_URL + quote_plus(query.strip())
    return f"{url}&{node}" if node else url


def _with_query(url: str, **extra: str) -> str:
    parts = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    params.update(extra)
    return urlunparse(parts._replace(query=urlencode(params)))


def _add_condition(url: str, condition: str) -> str:
    parts = urlparse(url)
    params = {k: v[0] for k, v in parse_qs(parts.query).items()}
    params["rh"] = f"{params['rh']},{condition}" if params.get("rh") else condition
    return urlunparse(parts._replace(query=urlencode(params)))


class AmazonScraper:
    slug = "amazon"

    def category_options(self, query: str, node: str | None = None) -> list[Category]:
        if node is None:
            with page() as tab:
                load_results(tab, _node_url(query, None), _RESULTS_SELECTOR)
                deps = tab.evaluate(_DEPARTMENTS_JS)
            return [Category(d["label"], f"i={d['alias']}") for d in deps]
        with page() as tab:
            load_results(tab, _node_url(query, node), _RESULTS_SELECTOR)
            links = tab.evaluate(_CATEGORY_LINKS_JS)
        seen, options = set(), []
        for link in links:
            token = _node_token(link["href"])
            if token and token not in seen:
                seen.add(token)
                options.append(Category(link["label"], token))
        return options

    def search(
        self,
        query: str,
        limit: int = 20,
        node: str | None = None,
        new_only: bool = True,
        page_num: int = 1,
    ) -> list[Listing]:
        # Keep Amazon's relevance sort: it front-loads the actual queried product,
        # whereas its price-asc sort ranks the whole category by price and buries the
        # product behind 100+ cheaper phones (unreachable, and the paging flags the
        # session). best_match sorts the front-loaded matches by price in code.
        url = _node_url(query, node)
        if new_only:
            url = _add_condition(url, _NOVO_CONDITION)
        url = _with_query(url, page=str(page_num))
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
