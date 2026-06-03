"""Shared stealth browser session built on Patchright, a patched/undetected
Playwright that avoids the Runtime.enable CDP leak.

Marketplaces block headless browsers, so the default mode runs a real Chromium
inside a virtual X display (Xvfb) — undetectable like a headed browser but with
no window, safe for unattended/cloud runs. A persistent profile makes the
fingerprint match a returning user; a challenge solved once (run --headed) is
remembered.
"""

import os
import random
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from patchright.sync_api import Page, sync_playwright

_PROFILE_DIR = Path(".browser-profile")

_playwright = None
_context = None
_xvfb = None
_mode = "virtual"  # virtual | headed | headless


def configure(mode: str = "virtual") -> None:
    """Set the run mode; call before the first page()."""
    global _mode
    _mode = mode


def _start_xvfb() -> tuple[subprocess.Popen | None, str | None]:
    """Start an Xvfb server on a free display; return (process, ':N')."""
    if not shutil.which("Xvfb"):
        print("Xvfb not installed; cannot run virtual display", file=sys.stderr)
        return None, None
    num = 99
    for _ in range(50):
        num = random.randint(100, 998)
        if not os.path.exists(f"/tmp/.X11-unix/X{num}"):
            break
    proc = subprocess.Popen(
        ["Xvfb", f":{num}", "-screen", "0", "1920x1080x24", "-nolisten", "tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(50):
        if os.path.exists(f"/tmp/.X11-unix/X{num}"):
            return proc, f":{num}"
        time.sleep(0.1)
    proc.terminate()
    return None, None


def _ensure_context():
    global _playwright, _context, _xvfb
    if _context is not None:
        return _context

    headless = _mode == "headless"
    browser_env = None
    if _mode == "virtual":
        _xvfb, display = _start_xvfb()
        if display:
            # Pin Chrome to the Xvfb display and drop Wayland so it can't surface
            # on the real session.
            browser_env = {k: v for k, v in os.environ.items() if k != "WAYLAND_DISPLAY"}
            browser_env["DISPLAY"] = display
        else:
            headless = not os.environ.get("DISPLAY")

    _PROFILE_DIR.mkdir(exist_ok=True)
    _playwright = sync_playwright().start()
    options = {
        "user_data_dir": str(_PROFILE_DIR),
        "headless": headless,
        "no_viewport": True,
        "locale": "pt-BR",
        "timezone_id": "America/Sao_Paulo",
    }
    if not headless:
        # Force the X11 backend so Chromium uses the X display instead of
        # auto-selecting Wayland (which it can't reach and won't fall back from).
        options["args"] = ["--ozone-platform=x11"]
    if browser_env is not None:
        options["env"] = browser_env
    _context = _playwright.chromium.launch_persistent_context(**options)
    return _context


@contextmanager
def page() -> Iterator[Page]:
    tab = _ensure_context().new_page()
    try:
        yield tab
    finally:
        tab.close()


def shutdown() -> None:
    global _playwright, _context, _xvfb
    if _context is not None:
        _context.close()
    if _playwright is not None:
        _playwright.stop()
    if _xvfb is not None:
        _xvfb.terminate()
        try:
            _xvfb.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _xvfb.kill()
    _playwright = _context = _xvfb = None
