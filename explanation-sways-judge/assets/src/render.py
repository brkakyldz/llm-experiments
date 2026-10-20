"""Render the README / post images with Playwright (Chromium), at 2x.

    python assets/src/render.py [--kit DIR]

result.png        from result.html, 1080x1350
trace-viewer.png  a screenshot of ../../trace-viewer.html, 1600x1000
experiment.png    from experiment.diagram.html, drawn with the architecture-diagram kit in the
                  frost theme (diagram-frost.css); only rendered when --kit points at the kit
                  folder that holds tokens.css, kit.css, icons.js and kit.js

The look is frost.css. The avatar in art/ was generated with an image model and holds no text;
every word and number is HTML. Fonts are Windows system fonts (Segoe UI Variable, Cascadia Mono),
so render on Windows. Nothing is loaded from the network."""

import argparse
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

SRC = Path(__file__).resolve().parent
ASSETS = SRC.parent
EXPERIMENT = ASSETS.parent

DIAGRAM = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<link rel="stylesheet" href="{kit}/tokens.css"><link rel="stylesheet" href="{kit}/kit.css">
<link rel="stylesheet" href="{src}/diagram-frost.css">
</head><body>
{fragment}
<script>document.fonts.forEach(f => f.load());</script>  <!-- the kit checks every face it names -->
<script src="{kit}/icons.js"></script>
<script src="{kit}/kit.js"></script>
</body></html>
"""

ap = argparse.ArgumentParser()
ap.add_argument("--kit", help="architecture-diagram kit folder; renders experiment.png when given")
ap.add_argument("--run", default="main/W18-explained-01", help="run the viewer screenshot opens")
args = ap.parse_args()

done = []
with sync_playwright() as p, tempfile.TemporaryDirectory() as tmp:
    browser = p.chromium.launch()

    page = browser.new_page(viewport={"width": 1080, "height": 1350}, device_scale_factor=2)
    page.goto((SRC / "result.html").as_uri())
    page.evaluate("document.fonts.ready")
    page.wait_for_function("[...document.images].every(i => i.complete)")
    page.wait_for_timeout(150)
    page.screenshot(path=str(ASSETS / "result.png"))
    done.append("result.png")

    viewer = EXPERIMENT / "trace-viewer.html"
    if viewer.exists():
        page = browser.new_page(viewport={"width": 1600, "height": 1000}, device_scale_factor=2)
        page.goto(viewer.as_uri())
        page.evaluate(f"selectRun({args.run!r})")
        page.evaluate("selectNode('judge')")  # the judge call, with the explanation highlighted
        page.evaluate("document.fonts.ready")
        page.wait_for_timeout(200)
        page.screenshot(path=str(ASSETS / "trace-viewer.png"))
        done.append("trace-viewer.png")

    if args.kit:
        kit = Path(args.kit).resolve()
        html = Path(tmp) / "experiment.html"
        html.write_text(DIAGRAM.format(kit=kit.as_uri(), src=SRC.as_uri(),
                                       fragment=(SRC / "experiment.diagram.html").read_text(encoding="utf-8")),
                        encoding="utf-8")
        page = browser.new_page(viewport={"width": 1800, "height": 1500}, device_scale_factor=2)
        page.goto(html.as_uri() + "?theme=frost")
        page.wait_for_function("window.__ready === true", timeout=20000)
        for w in page.evaluate("window.__warnings"):
            print("  WARN experiment:", w)
        page.locator(".canvas").screenshot(path=str(ASSETS / "experiment.png"))
        done.append("experiment.png")

    browser.close()
print("rendered " + ", ".join(done))
