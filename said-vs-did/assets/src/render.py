"""Render the README / post images with Playwright (Chromium).

    python assets/src/render.py [--fonts DIR]

judge-passed.png  from judge-passed.html, 1080x1350 at 2x
trace-viewer.png  a screenshot of ../../trace-viewer.html, 1600x1000 at 2x
three-graders.png is drawn separately with an architecture-diagram kit; its source is
three-graders.diagram.html.

The fonts are Inter and JetBrains Mono (SIL OFL 1.1). Point --fonts at a folder that holds
Inter.ttf and JetBrainsMono.ttf."""

import argparse
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
ASSETS = SRC.parent
EXPERIMENT = ASSETS.parent

ap = argparse.ArgumentParser()
ap.add_argument("--fonts", default="C:/berke-skills/skills/arch-diagram/kit/fonts")
args = ap.parse_args()
fonts = Path(args.fonts).resolve().as_uri()

with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    browser = p.chromium.launch()

    page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
    html = Path(tmp) / "judge-passed.html"
    html.write_text((SRC / "judge-passed.html").read_text(encoding="utf-8").replace("{FONTS}", fonts), encoding="utf-8")
    page.goto(html.as_uri())
    page.evaluate("document.fonts.ready")
    page.screenshot(path=str(ASSETS / "judge-passed.png"))

    page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
    page.goto((EXPERIMENT / "trace-viewer.html").as_uri() + "#loose-main/counterfactual-04")
    page.click('[data-node="s2"]')  # get_order_details: where the leaked word came from
    page.wait_for_timeout(200)
    page.screenshot(path=str(ASSETS / "trace-viewer.png"))

    browser.close()
print("rendered judge-passed.png, trace-viewer.png")
