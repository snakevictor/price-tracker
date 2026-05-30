"""Shared headless-Chromium session built on Playwright's sync API.

Chromium starts lazily on first use and one browser context is reused across
all scraper calls in the process. Call `shutdown()` when done.
"""

from collections.abc import Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

_playwright = None
_browser = None
_context = None
_headless = True


def configure(headless: bool) -> None:
    """Set headless mode. Must be called before the first page() call."""
    global _headless
    _headless = headless


def _ensure_context():
    global _playwright, _browser, _context
    if _context is not None:
        return _context
    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(
        headless=_headless,
        args=["--disable-blink-features=AutomationControlled"],
    )
    _context = _browser.new_context(
        user_agent=_USER_AGENT,
        locale="pt-BR",
        viewport={"width": 1366, "height": 768},
    )
    _context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return _context


@contextmanager
def page() -> Iterator[Page]:
    tab = _ensure_context().new_page()
    try:
        yield tab
    finally:
        tab.close()


def shutdown() -> None:
    global _playwright, _browser, _context
    if _context is not None:
        _context.close()
    if _browser is not None:
        _browser.close()
    if _playwright is not None:
        _playwright.stop()
    _playwright = _browser = _context = None
