"""Icono de DropWheel (rueda de vidrio sobre fondo oscuro). Lo usan la bandeja y el instalador."""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageFilter


def make_icon(size: int = 256) -> Image.Image:
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # cuadrado redondeado oscuro
    pad = int(S * 0.04)
    d.rounded_rectangle([pad, pad, S - pad, S - pad], radius=int(S * 0.22), fill=(22, 24, 30, 255))
    # leve brillo superior
    glow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse([S * 0.1, -S * 0.35, S * 0.9, S * 0.45], fill=(255, 255, 255, 28))
    glow = glow.filter(ImageFilter.GaussianBlur(S * 0.05))
    mask = Image.new("L", (S, S), 0)
    ImageDraw.Draw(mask).rounded_rectangle([pad, pad, S - pad, S - pad], radius=int(S * 0.22), fill=255)
    glow.putalpha(Image.composite(glow.getchannel("A"), Image.new("L", (S, S), 0), mask))
    img = Image.alpha_composite(img, glow)
    d = ImageDraw.Draw(img)
    cx = cy = S / 2
    r_out, r_in, n = S * 0.36, S * 0.15, 6
    for i in range(n):
        a0 = -90 + i * 360 / n - 180 / n
        a1 = a0 + 360 / n
        gap = S * 0.012
        pts = []
        for k in range(21):
            t = math.radians(a0 + (a1 - a0) * k / 20 + (math.degrees(gap / r_out) if k == 0 else 0))
            pts.append((cx + r_out * math.cos(t), cy + r_out * math.sin(t)))
        for k in range(21):
            t = math.radians(a1 - (a1 - a0) * k / 20)
            pts.append((cx + r_in * math.cos(t), cy + r_in * math.sin(t)))
        hot = i == 1
        d.polygon(pts, fill=(124, 196, 255, 255) if hot else (235, 238, 245, 235 if i % 2 else 205))
    d.ellipse([cx - r_in * 0.78, cy - r_in * 0.78, cx + r_in * 0.78, cy + r_in * 0.78], fill=(22, 24, 30, 255))
    return img.resize((size, size), Image.LANCZOS)


def save_ico(path: str) -> None:
    big = make_icon(256)
    big.save(path, format="ICO", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
