# -*- coding: utf-8 -*-
"""Пакує PNG-кадри з coin.py у WebP з альфою і PNG-спрайти.

Запуск (потрібен Pillow і numpy у системному Python, у .venv їх немає):
  python mascot\\pack_coin.py [--frames DIR]

DIR типово %TEMP%\\coin-frames (туди ж пише coin.py). Результат: assets\\coin\\.
"""
import argparse
import os
import sys
import tempfile

import numpy as np
from PIL import Image, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "coin")

# назва: (тека кадрів, кількість, розмір, мс на кадр, ліміт КБ)
ANIMS = {
    "coin-spin": ("spin", 24, 160, 42, 350),
    "coin-flip": ("flip", 12, 160, 50, 200),
    "coin-burst": ("burst", 14, 200, 50, 300),
}
WEBP = dict(lossless=False, quality=85, method=6)
# якість WebP по файлах: 80 тримає spin, flip і still у межах ваги першої версії
QUALITY = {"coin-spin": 80, "coin-flip": 80, "coin-burst": 85, "coin-still": 80}


def downscale(path, size):
    """Зменшення в премультиплікованому просторі: без темної облямівки на краю альфи."""
    im = Image.open(path).convert("RGBA")
    return im.convert("RGBa").resize((size, size), Image.LANCZOS).convert("RGBA")


def bloom(im, radii=(2, 7), gains=(0.6, 0.6), strength=0.9):
    """Сяйво для спалаху: розмита копія додається до кольору і до альфи."""
    a = np.asarray(im, dtype=np.float32) / 255.0
    alpha = a[..., 3:4]
    prem = a[..., :3] * alpha
    # джерело сяйва: лише яскраве понад поріг, щоб монета не вигоряла в білий диск
    peak = prem.max(axis=-1, keepdims=True)
    src = prem * np.clip((peak - 0.65) / 0.35, 0, 1)
    glow = np.zeros_like(prem)
    for r, g in zip(radii, gains):
        chans = []
        for c in range(3):
            ch = Image.fromarray((src[..., c] * 255).astype(np.uint8), "L")
            chans.append(np.asarray(ch.filter(ImageFilter.GaussianBlur(r)), dtype=np.float32) / 255.0)
        glow += np.stack(chans, axis=-1) * g
    glow *= strength
    # альфа сяйва: за найяскравішим каналом розмитого кольору
    lum = glow.max(axis=-1, keepdims=True)
    out_rgb = prem + glow
    out_a = np.clip(alpha + lum * 0.85, 0, 1)
    out_rgb = np.clip(out_rgb, 0, 1)
    rgb = np.where(out_a > 1e-4, out_rgb / np.maximum(out_a, 1e-4), 0)
    res = np.concatenate([np.clip(rgb, 0, 1), out_a], axis=-1)
    return Image.fromarray((res * 255 + 0.5).astype(np.uint8), "RGBA")


def save_anim(name, frames, ms):
    path = os.path.join(OUT, name + ".webp")
    opts = dict(WEBP, quality=QUALITY[name])
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=ms, loop=0, **opts)
    sheet = Image.new("RGBA", (frames[0].width * len(frames), frames[0].height), (0, 0, 0, 0))
    for i, f in enumerate(frames):
        sheet.paste(f, (i * f.width, 0))
    # запасний спрайт: палітра 256 кольорів з альфою і дизерингом, у 4-6 разів легший за RGBA
    pal = sheet.quantize(colors=256, method=Image.Quantize.FASTOCTREE, dither=Image.Dither.FLOYDSTEINBERG)
    pal.save(os.path.join(OUT, name + "-sprite.png"), optimize=True)
    n = Image.open(path).n_frames
    kb = os.path.getsize(path) / 1024
    print("%-11s %2d кадрів  %.1f КБ  спрайт %dx%d" % (name, n, kb, sheet.width, sheet.height))
    if n != len(frames):
        sys.exit("ПОМИЛКА: %s містить %d кадрів замість %d" % (name, n, len(frames)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", default=os.path.join(tempfile.gettempdir(), "coin-frames"))
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)

    still = downscale(os.path.join(args.frames, "still", "still.png"), 256)
    still.save(os.path.join(OUT, "coin-still.webp"), **dict(WEBP, quality=QUALITY["coin-still"]))
    print("coin-still  %.1f КБ" % (os.path.getsize(os.path.join(OUT, "coin-still.webp")) / 1024))

    for name, (sub, count, size, ms, _limit) in ANIMS.items():
        frames = [downscale(os.path.join(args.frames, sub, "f%02d.png" % i), size) for i in range(count)]
        if sub == "burst":
            # кадр 0 це звичайна монета (стик із перельотом), сяйво наростає з кадру 1
            ramp = [0.0, 0.5, 1.0, 1.0, 0.95, 0.9, 0.85, 0.8, 0.75, 0.7, 0.7, 0.7, 0.7, 0.7]
            frames = [f if k == 0 else bloom(f, strength=ramp[k]) for k, f in enumerate(frames)]
        save_anim(name, frames, ms)


if __name__ == "__main__":
    main()
