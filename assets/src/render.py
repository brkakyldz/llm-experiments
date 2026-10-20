"""Render this page's images with Playwright (Chromium), at 2x, as JPEG.

    python assets/src/render.py

banner.jpg                          from banner.html
cards/explanation-sways-judge.jpg   from card-esj.html
cards/said-vs-did.jpg               from card-svd.html

The avatar under art/ (the reader, a small robot) was generated with an image model and
holds no text. Every word and number is HTML over it, taken from each experiment's README. The
look is frost.css; fonts are Windows system fonts (Segoe UI Variable, Cascadia Mono), so render on
Windows. Nothing is loaded from the network."""

from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
ASSETS = SRC.parent

PAGES = [
    ("banner.html", "banner.jpg", 1280, 440),
    ("card-esj.html", "cards/explanation-sways-judge.jpg", 1280, 660),
    ("card-svd.html", "cards/said-vs-did.jpg", 1280, 660),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(device_scale_factor=2)
    for src, out, w, h in PAGES:
        page.set_viewport_size({"width": w, "height": h})
        page.goto((SRC / src).as_uri())
        page.evaluate("document.fonts.ready")
        page.wait_for_function("[...document.images].every(i => i.complete)")
        page.wait_for_timeout(250)
        dest = ASSETS / out
        dest.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(dest), type="jpeg", quality=90)
        print(dest.relative_to(ASSETS.parent))
    browser.close()
