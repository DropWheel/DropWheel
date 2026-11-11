"""Paleta adaptativa: toma el color dominante del fondo (lo que hay detrás de la rueda) y decide
si el vidrio es oscuro o claro, qué color de resalte usar y de qué color va el texto.

Puro Pillow/colorsys: se prueba igual en cualquier sistema.
"""
from __future__ import annotations

import colorsys
import json
import os
from dataclasses import asdict, dataclass

RGB = tuple


def _clamp(v, lo=0.0, hi=1.0):
    return max(lo, min(hi, v))


def mix(a: RGB, b: RGB, t: float) -> RGB:
    return tuple(int(round(a[i] + (b[i] - a[i]) * t)) for i in range(3))


def luminance(c: RGB) -> float:
    r, g, b = [v / 255.0 for v in c[:3]]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def hex_to_rgb(h: str) -> RGB:
    h = h.strip().lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


@dataclass
class Palette:
    dark: bool
    tint: RGB          # color base del vidrio (lleva el tono del fondo)
    tint_deep: RGB     # versión más profunda (centro, barra de páginas)
    accent: RGB        # resalte del segmento activo
    accent_hi: RGB
    accent_lo: RGB
    on_accent: RGB     # texto sobre el resalte
    text: RGB
    muted: RGB
    neutral_accent: bool = False

    def to_json(self) -> str:
        return json.dumps(asdict(self))

    @classmethod
    def from_json(cls, s: str) -> "Palette":
        d = json.loads(s)
        for k, v in list(d.items()):
            if isinstance(v, list):
                d[k] = tuple(v)
        return cls(**d)


def _vivid(c: RGB, dark: bool) -> RGB:
    h, s, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in c])
    s = _clamp(max(s, 0.55))
    v = _clamp(max(v, 0.88 if dark else 0.72), 0, 1)
    return tuple(int(round(x * 255)) for x in colorsys.hsv_to_rgb(h, s, v))


def _pick_accent(small, dark: bool) -> RGB | None:
    """Color más 'llamativo' del fondo (saturado y frecuente). None si el fondo es casi monocromo."""
    q = small.quantize(colors=8, method=0)  # 0 = MEDIANCUT
    pal = q.getpalette()[:24]
    counts = sorted(q.getcolors() or [], reverse=True)
    total = float(sum(n for n, _ in counts)) or 1.0
    best, best_score = None, 0.0
    for n, idx in counts:
        c = tuple(pal[idx * 3: idx * 3 + 3])
        h, s, v = colorsys.rgb_to_hsv(*[x / 255.0 for x in c])
        if s < 0.30 or v < 0.28:
            continue
        score = (n / total) ** 0.6 * s ** 1.4 * (0.5 + v)
        if score > best_score:
            best, best_score = c, score
    return best


def from_image(img, style: str = "auto", accent=None) -> Palette:
    """Construye la paleta a partir de la imagen de fondo (PIL).

    style: 'auto' | 'dark' | 'light'.  accent: None/'auto' | '#rrggbb' | (r, g, b).
    """
    small = img.convert("RGB").resize((48, 48))
    px = list(small.getdata())
    avg = tuple(int(sum(p[i] for p in px) / len(px)) for i in range(3))
    lum = luminance(avg)
    dark = (lum < 0.55) if style == "auto" else style == "dark"

    h, l, s = colorsys.rgb_to_hls(*[x / 255.0 for x in avg])
    s = _clamp(s * 1.15, 0, 0.75)
    if dark:
        l2 = _clamp(l * 0.5 + 0.03, 0.085, 0.20)  # nunca más negro que el fondo: se necesita contraste
    else:
        l2 = _clamp(0.80 + l * 0.15, 0.83, 0.95)
    tint = tuple(int(round(x * 255)) for x in colorsys.hls_to_rgb(h, l2, s))
    deep = mix(tint, (0, 0, 0), 0.45) if dark else mix(tint, (0, 0, 0), 0.18)

    acc = None
    if isinstance(accent, str) and accent.startswith("#"):
        acc = hex_to_rgb(accent)
    elif isinstance(accent, (tuple, list)):
        acc = tuple(accent)
    neutral = False
    if acc is None:
        found = _pick_accent(small, dark)
        if found is not None:
            acc = _vivid(found, dark)
        else:
            neutral = True
            acc = (236, 238, 245) if dark else (36, 38, 48)
    on_accent = (20, 22, 28) if luminance(acc) > 0.58 else (255, 255, 255)
    acc_hi = mix(acc, (255, 255, 255), 0.22 if not neutral else 0.0)
    acc_lo = mix(acc, (0, 0, 0), 0.22 if not neutral else 0.14)
    text = (246, 247, 250) if dark else (28, 30, 38)
    muted = mix(text, tint, 0.45)
    return Palette(dark, tint, deep, acc, acc_hi, acc_lo, on_accent, text, muted, neutral)


def default_palette() -> Palette:
    """Vidrio oscuro neutro (sirve cuando no hay fondo que leer)."""
    from PIL import Image

    return from_image(Image.new("RGB", (8, 8), (14, 14, 16)))


def from_env() -> Palette | None:
    raw = os.environ.get("DROPWHEEL_PALETTE")
    if not raw:
        return None
    try:
        return Palette.from_json(raw)
    except Exception:  # noqa: BLE001
        return None


def wallpaper_palette(style: str = "auto", accent=None) -> Palette:
    """Paleta a partir del fondo de escritorio (Windows); si no se puede leer, vidrio oscuro neutro."""
    try:
        import winreg  # type: ignore

        from PIL import Image

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop") as k:
            path = winreg.QueryValueEx(k, "WallPaper")[0]
        if not path or not os.path.exists(path):
            path = os.path.join(os.environ.get("APPDATA", ""), r"Microsoft\Windows\Themes\TranscodedWallpaper")
        with Image.open(path) as im:
            im.draft("RGB", (160, 160))
            return from_image(im.convert("RGB"), style, accent)
    except Exception:  # noqa: BLE001
        return default_palette()
