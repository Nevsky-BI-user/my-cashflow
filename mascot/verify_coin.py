# -*- coding: utf-8 -*-
"""Перевірка ассетів монети: розміри, альфа, вага, кадри, шов петлі coin-spin.

Запуск: python mascot\\verify_coin.py [--frames DIR]
З --frames (типово %TEMP%\\coin-frames, якщо є) ще звіряє контрольний кадр
360 градусів (spin\\f24.png) з кадром 0 градусів: петля без шва за побудовою.
"""
import argparse
import glob
import os
import sys
import tempfile

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "assets", "coin")

# файл: (кадрів, сторона, ліміт КБ або None)
SPEC = {
    "coin-spin.webp": (24, 160, 350),
    "coin-flip.webp": (12, 160, 200),
    "coin-burst.webp": (14, 200, 300),
    "coin-still.webp": (1, 256, 60),
}
fails = []


def check(ok, msg):
    print(("OK   " if ok else "FAIL ") + msg)
    if not ok:
        fails.append(msg)


def frames_of(path):
    im = Image.open(path)
    out = []
    for i in range(getattr(im, "n_frames", 1)):
        im.seek(i)
        out.append(np.asarray(im.convert("RGBA"), dtype=np.float32))
    return im, out


def diff(a, b):
    """Середня абсолютна різниця RGBA у пікселях 0..255."""
    return float(np.abs(a - b).mean())


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=os.path.join(tempfile.gettempdir(), "coin-frames"))
    args = ap.parse_args()

    for name, (n, side, limit) in SPEC.items():
        path = os.path.join(ASSETS, name)
        if not os.path.exists(path):
            check(False, "%s існує" % name)
            continue
        kb = os.path.getsize(path) / 1024
        im, fr = frames_of(path)
        alpha_ok = all(f[..., 3].min() == 0 and f[..., 3].max() == 255 for f in fr[:1]) and \
            all(f[..., 3].min() == 0 for f in fr)
        check(im.size == (side, side), "%s розмір %dx%d (треба %dx%d)" % (name, im.size[0], im.size[1], side, side))
        check(len(fr) == n, "%s кадрів %d (треба %d)" % (name, len(fr), n))
        check(kb <= limit, "%s вага %.1f КБ (ліміт %d КБ)" % (name, kb, limit))
        check(im.mode in ("RGBA",) or "A" in im.mode or alpha_ok, "%s режим %s" % (name, im.mode))
        check(alpha_ok, "%s альфа: прозоре тло в кожному кадрі, непрозора монета в кадрі 1" % name)
        empty = [i + 1 for i, f in enumerate(fr) if f[..., 3].max() == 0]
        check(not empty, "%s порожніх кадрів немає %s" % (name, empty or ""))

        if name != "coin-still.webp":
            sp = os.path.join(ASSETS, name.replace(".webp", "-sprite.png"))
            s = Image.open(sp)
            sa = np.asarray(s.convert("RGBA"))[..., 3]
            check(s.size == (side * n, side) and s.mode in ("RGBA", "P") and sa.min() == 0 and sa.max() == 255,
                  "%s спрайт %dx%d %s, альфа є" % (os.path.basename(sp), s.size[0], s.size[1], s.mode))

        if name == "coin-spin.webp":
            steps = [diff(fr[i], fr[i + 1]) for i in range(n - 1)]
            seam = diff(fr[n - 1], fr[0])
            mean = sum(steps) / len(steps)
            print("     сусідні кадри: середнє %.2f, мін %.2f, макс %.2f" % (mean, min(steps), max(steps)))
            print("     шов кадр 24 -> кадр 1: %.2f (відношення до середнього кроку %.2f)" % (seam, seam / mean))
            check(seam <= max(steps) * 1.05, "coin-spin шов у межах звичайного кроку між кадрами")

    raw0 = os.path.join(args.frames, "spin", "f00.png")
    raw24 = os.path.join(args.frames, "spin", "f24.png")
    if os.path.exists(raw0) and os.path.exists(raw24):
        a = np.asarray(Image.open(raw0).convert("RGBA"), dtype=np.float32)
        b = np.asarray(Image.open(raw24).convert("RGBA"), dtype=np.float32)
        d = diff(a, b)
        print("     рендер 360 градусів проти 0 градусів: різниця %.3f" % d)
        check(d < 0.5, "петля замкнена: кадр 360 градусів збігається з кадром 0 градусів")
    else:
        print("SKIP контрольний кадр 360 градусів: немає %s" % raw24)

    bad = []
    for f in glob.glob(os.path.join(ROOT, "mascot", "*")):
        if os.path.isfile(f) and f.endswith((".py", ".html", ".md")):
            t = open(f, encoding="utf-8").read()
            if chr(0x2014) in t or chr(0x2013) in t:
                bad.append(os.path.basename(f))
    check(not bad, "довгих і коротких тире у mascot\\ немає %s" % (bad or ""))

    print("\nПІДСУМОК: %s" % ("усе гаразд" if not fails else "%d помилок" % len(fails)))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
