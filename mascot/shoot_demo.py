# -*- coding: utf-8 -*-
"""Знімки демо монети в headless Chromium без звуку.

Запуск: .venv\\Scripts\\python.exe mascot\\shoot_demo.py
Пише mascot\\shots\\: flight-150.png, flight-300.png, flight-450.png,
burst-mid.png, end.png, reduced-motion.png.
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
SHOTS = HERE / "shots"
URL = (HERE / "coin-demo.html").as_uri()

WAIT_FRAMES = "new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))"
# площа перетину елемента з сумою на картці рахунку, по панелях
OVERLAP = """sel => Array.from(document.querySelectorAll('[data-panel]')).map(p => {
  const el = p.querySelector(sel); if (!el) return -1;
  const a = el.getBoundingClientRect(), b = p.querySelector('[data-sum="target"]').getBoundingClientRect();
  const w = Math.min(a.right, b.right) - Math.max(a.left, b.left);
  const h = Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top);
  return w > 0 && h > 0 ? Math.round(w * h) : 0; })"""
IMAGES_READY = "Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)"


def sums(page):
    return page.eval_on_selector_all("[data-sum]", "els => els.map(e => e.textContent)")


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    SHOTS.mkdir(exist_ok=True)
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--mute-audio"])
        try:
            ctx = browser.new_context(viewport={"width": 1100, "height": 470})
            page = ctx.new_page()
            page.on("console", lambda m: m.type == "error" and errors.append(m.text))
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            page.wait_for_function(IMAGES_READY)
            print("старт:", sums(page))

            page.click("#go")
            page.evaluate("coinDemo.anims.forEach(a => a.pause())")
            for t in (150, 300, 450):
                page.evaluate("t => coinDemo.anims.forEach(a => { a.currentTime = t; })", t)
                page.evaluate(WAIT_FRAMES)
                page.screenshot(path=str(SHOTS / ("flight-%d.png" % t)))
                print("переліт %d мс:" % t, sums(page))

            # перед приземленням: монета не перекриває суму на картці рахунку
            page.evaluate("coinDemo.anims.forEach(a => { a.currentTime = 599; })")
            page.evaluate(WAIT_FRAMES)
            overlap = page.evaluate(OVERLAP, ".coin-fly")
            print("монета над сумою перед приземленням, px2 перетину:", overlap)
            if any(overlap):
                errors.append("монета перекриває суму: %s" % overlap)

            # дограємо переліт, ловимо середину спалаху
            page.evaluate("coinDemo.anims.forEach(a => a.play())")
            page.wait_for_selector(".coin-burst")
            page.evaluate("""() => document.getAnimations()
                .filter(a => a.animationName === 'coin-burst')
                .forEach(a => { a.pause(); a.currentTime = 200; })""")
            page.evaluate(WAIT_FRAMES)
            page.screenshot(path=str(SHOTS / "burst-mid.png"))
            overlap = page.evaluate(OVERLAP, ".coin-burst")
            print("спалах над сумою, px2 перетину:", overlap)
            if any(overlap):
                errors.append("спалах перекриває суму: %s" % overlap)
            page.evaluate("document.getAnimations().forEach(a => a.play())")
            page.evaluate("coinDemo.done")
            page.evaluate(WAIT_FRAMES)
            page.screenshot(path=str(SHOTS / "end.png"))
            left = page.evaluate("document.querySelectorAll('.coin-fly, .coin-burst').length")
            print("кінець:", sums(page), "залишків анімації:", left)
            ctx.close()

            # prefers-reduced-motion: одразу кінцевий стан, без монети в польоті
            ctx = browser.new_context(viewport={"width": 1100, "height": 470}, reduced_motion="reduce")
            page = ctx.new_page()
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(URL)
            page.wait_for_function(IMAGES_READY)
            page.click("#go")
            page.evaluate(WAIT_FRAMES)
            flying = page.evaluate("document.querySelectorAll('.coin-fly, .coin-burst').length")
            page.screenshot(path=str(SHOTS / "reduced-motion.png"))
            print("reduced-motion одразу:", sums(page), "монет у польоті:", flying)
            ctx.close()
        finally:
            browser.close()
    print("помилки консолі:", errors or "немає")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
