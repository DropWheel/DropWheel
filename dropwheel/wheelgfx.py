"""Dibujo de la rueda con Pillow (sin ventanas ni Windows: se puede probar en cualquier SO).

Estilo "vidrio esmerilado": se toma lo que hay detrás de la rueda, se desenfoca y se tiñe con el color
dominante del fondo (paleta de colors.py). Con un fondo casi negro queda vidrio oscuro; el segmento
activo se resalta con el color más vivo del fondo (o un blanco suave si el fondo es monocromo).
Todo se dibuja a 2x y se reduce para que los bordes salgan suaves.
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

from .colors import Palette, default_palette

SS = 2  # supersampling

# Geometría base (px lógicos). Se multiplica por `scale` según el DPI y el tamaño elegido.
R_OUT = 186
R_IN = 62
GAP = 2.4           # separación entre segmentos (px)
MARGIN = 30         # espacio alrededor para sombra y para el "salto" del segmento activo
POP = 9             # cuánto sobresale el segmento activo
PILL_H = 40         # alto de la franja inferior con el indicador de página


def _font(px: int, bold: bool = True):
    names = (["segoeuib.ttf", "seguisb.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, px)
        except OSError:
            continue
    try:
        return ImageFont.load_default(px)
    except TypeError:
        return ImageFont.load_default()


def _vgradient(size, top, bottom, alpha=255):
    w, h = size
    col = Image.new("RGBA", (1, max(1, h)))
    px = col.load()
    for y in range(max(1, h)):
        t = y / max(1, h - 1)
        px[0, y] = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (alpha,)
    return col.resize((w, h))


def _sector_points(cx, cy, r_out, r_in, a0, a1, gap):
    """Polígono de un sector anular entre los ángulos a0..a1 (grados, 0 = derecha, horario)."""
    pts = []
    da_out = math.degrees(gap / 2 / r_out)
    da_in = math.degrees(gap / 2 / r_in)
    step = 2.0
    a, end = a0 + da_out, a1 - da_out
    n = max(2, int((end - a) / step))
    for i in range(n + 1):
        t = math.radians(a + (end - a) * i / n)
        pts.append((cx + r_out * math.cos(t), cy + r_out * math.sin(t)))
    a, end = a1 - da_in, a0 + da_in
    n = max(2, int((a - end) / step))
    for i in range(n + 1):
        t = math.radians(a - (a - end) * i / n)
        pts.append((cx + r_in * math.cos(t), cy + r_in * math.sin(t)))
    return pts


# ------------------------------------------------------------------- iconos
def draw_icon(d: ImageDraw.ImageDraw, name: str, cx: float, cy: float, s: float, color, w: int):
    """Iconos simples de línea. `s` = medio ancho del icono."""
    c = color
    if name == "COMPRESS":
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            ex, ey = cx + sx * s, cy + sy * s
            d.line([(ex, ey), (cx + sx * s * 0.25, cy + sy * s * 0.25)], fill=c, width=w)
            d.line([(cx + sx * s * 0.25, cy + sy * s * 0.25), (cx + sx * s * 0.25, cy + sy * s * 0.75)], fill=c, width=w)
            d.line([(cx + sx * s * 0.25, cy + sy * s * 0.25), (cx + sx * s * 0.75, cy + sy * s * 0.25)], fill=c, width=w)
    elif name == "METADATA":
        pts = [(cx - s, cy), (cx - s * 0.2, cy - s * 0.9), (cx + s, cy - s * 0.9), (cx + s, cy + s * 0.9), (cx - s * 0.2, cy + s * 0.9)]
        d.line(pts + [pts[0]], fill=c, width=w, joint="curve")
        d.ellipse([cx + s * 0.35 - w, cy - w, cx + s * 0.35 + w, cy + w], outline=c, width=max(1, w - 1))
    elif name == "EDIT":
        d.line([(cx - s, cy + s), (cx + s * 0.8, cy - s * 0.8)], fill=c, width=w * 2)
        d.polygon([(cx - s * 1.05, cy + s * 1.05), (cx - s * 0.95, cy + s * 0.35), (cx - s * 0.35, cy + s * 0.95)], fill=c)
    elif name == "ANNOTATE":
        d.rounded_rectangle([cx - s, cy - s * 0.85, cx + s, cy + s * 0.55], radius=s * 0.3, outline=c, width=w)
        d.polygon([(cx - s * 0.3, cy + s * 0.5), (cx - s * 0.65, cy + s * 1.0), (cx + s * 0.1, cy + s * 0.5)], fill=c)
    elif name == "ADD BG":
        d.rounded_rectangle([cx - s, cy - s * 0.85, cx + s, cy + s * 0.85], radius=s * 0.18, outline=c, width=w)
        d.polygon([(cx - s * 0.85, cy + s * 0.7), (cx - s * 0.25, cy - s * 0.05), (cx + s * 0.15, cy + s * 0.4),
                   (cx + s * 0.45, cy + s * 0.05), (cx + s * 0.85, cy + s * 0.7)], fill=c)
        d.ellipse([cx + s * 0.35 - w, cy - s * 0.5 - w, cx + s * 0.35 + w, cy - s * 0.5 + w], fill=c)
    elif name == "CROP":
        d.line([(cx - s * 0.5, cy - s), (cx - s * 0.5, cy + s * 0.5), (cx + s, cy + s * 0.5)], fill=c, width=w, joint="curve")
        d.line([(cx - s, cy - s * 0.5), (cx + s * 0.5, cy - s * 0.5), (cx + s * 0.5, cy + s)], fill=c, width=w, joint="curve")
    elif name == "REDACT":
        d.ellipse([cx - s, cy - s * 0.55, cx + s, cy + s * 0.55], outline=c, width=w)
        d.ellipse([cx - s * 0.28, cy - s * 0.28, cx + s * 0.28, cy + s * 0.28], fill=c)
        d.line([(cx - s * 0.9, cy + s * 0.9), (cx + s * 0.9, cy - s * 0.9)], fill=c, width=w)


def _pretty(name: str) -> str:
    return {"COMPRESS": "Compress", "METADATA": "Metadata", "EDIT": "Edit", "ANNOTATE": "Annotate",
            "ADD BG": "Add BG", "CROP": "Crop", "REDACT": "Redact"}.get(name, name)


class Wheel:
    """Rueda con N segmentos. Crear una por (labels, scale); render() es rápido."""

    def __init__(self, labels: list[str], scale: float = 1.0, icons: bool = False,
                 palette: Palette | None = None, backdrop: Image.Image | None = None):
        self.labels = list(labels)
        self.n = max(1, len(self.labels))
        self.scale = scale
        self.icons = icons
        self.pal = palette or default_palette()
        self.backdrop = backdrop
        self.r_out = R_OUT * scale
        self.r_in = R_IN * scale
        self.margin = MARGIN * scale
        self.W = int(round(2 * (self.r_out + self.margin)))
        self.pill_h = int(round(PILL_H * scale))
        self.H = self.W + self.pill_h
        self.cx = self.W / 2
        self.cy = self.W / 2
        self.span = 360.0 / self.n
        self._base: Image.Image | None = None
        self._hot: dict[int, Image.Image] = {}

    # ---------------------------------------------------------------- geometría
    def angle_of(self, i: int) -> float:
        """Ángulo central (grados, 0 = derecha, horario) del segmento i; el 0 queda arriba."""
        return -90.0 + i * self.span

    def hit_test(self, x: float, y: float):
        """x, y relativos a la ventana. Devuelve índice de segmento, 'hub' o None."""
        dx, dy = x - self.cx, y - self.cy
        r = math.hypot(dx, dy)
        if r < self.r_in:
            return "hub"
        if r > self.r_out + 4 * self.scale:
            return None
        ang = (math.degrees(math.atan2(dy, dx)) + 90.0 + self.span / 2) % 360.0
        return int(ang // self.span) % self.n

    # ---------------------------------------------------------------- dibujo
    def _canvas(self):
        return Image.new("RGBA", (self.W * SS, self.H * SS), (0, 0, 0, 0))

    def _segment_mask(self, i: int, r_out: float | None = None):
        m = Image.new("L", (self.W * SS, self.H * SS), 0)
        a = self.angle_of(i)
        pts = _sector_points(self.cx * SS, self.cy * SS, (r_out or self.r_out) * SS, self.r_in * SS,
                             a - self.span / 2, a + self.span / 2, GAP * self.scale * SS)
        ImageDraw.Draw(m).polygon(pts, fill=255)
        return m

    def _label_layer(self, i: int, color, shadow: bool):
        layer = self._canvas()
        d = ImageDraw.Draw(layer)
        a = math.radians(self.angle_of(i))
        rm = (self.r_out + self.r_in) / 2 + 2 * self.scale
        x = (self.cx + rm * math.cos(a)) * SS
        y = (self.cy + rm * math.sin(a)) * SS
        name = self.labels[i]
        sh = (0, 0, 0, 150)
        off = 1.4 * self.scale * SS
        if self.icons:
            s = 9 * self.scale * SS
            wline = max(2, int(1.6 * self.scale * SS))
            f = _font(int(11.5 * self.scale * SS))
            if shadow:
                draw_icon(d, name, x, y - 9 * self.scale * SS + off, s, sh, wline)
                d.text((x, y + 15 * self.scale * SS + off), _pretty(name), font=f, fill=sh, anchor="mm")
            draw_icon(d, name, x, y - 9 * self.scale * SS, s, color, wline)
            d.text((x, y + 15 * self.scale * SS), _pretty(name), font=f, fill=color, anchor="mm")
        else:
            size = int((16 if len(name) <= 4 else 13.5) * self.scale * SS)
            f = _font(size)
            if shadow:
                d.text((x, y + off), name, font=f, fill=sh, anchor="mm")
            d.text((x, y), name, font=f, fill=color, anchor="mm")
        return layer

    def _glass(self) -> Image.Image:
        """Fondo de vidrio: lo de atrás desenfocado + tinte del color dominante + brillo superior."""
        W, H = self.W * SS, self.H * SS
        pal = self.pal
        if self.backdrop is not None:
            bd = self.backdrop.convert("RGB").resize((self.W, self.H), Image.BILINEAR)
            bd = bd.filter(ImageFilter.GaussianBlur(9 * self.scale))
            bd = ImageEnhance.Color(bd).enhance(1.2)
            bd = bd.resize((W, H), Image.BILINEAR)
        else:
            bd = Image.new("RGB", (W, H), pal.tint)
        tint = Image.new("RGB", (W, H), pal.tint)
        glass = Image.blend(bd, tint, 0.64 if pal.dark else 0.58).convert("RGBA")
        # brillo: degradado blanco suave de arriba hacia abajo
        top_a = 46 if pal.dark else 95
        sheen = Image.new("RGBA", (1, H))
        px = sheen.load()
        for y in range(H):
            t = max(0.0, 1.0 - y / (H * 0.62))
            px[0, y] = (255, 255, 255, int(top_a * t * t))
        glass = Image.alpha_composite(glass, sheen.resize((W, H)))
        glass.putalpha(250)
        return glass

    def base(self) -> Image.Image:
        """Rueda sin resaltado ni centro, ya a tamaño final (ahorra RAM)."""
        if self._base is not None:
            return self._base
        pal = self.pal
        W, H = self.W * SS, self.H * SS
        img = self._canvas()
        r = self.r_out * SS
        cx, cy = self.cx * SS, self.cy * SS
        # Sombra suave y neutra debajo de toda la rueda
        sh = Image.new("L", (W, H), 0)
        ImageDraw.Draw(sh).ellipse([cx - r, cy - r + 7 * self.scale * SS, cx + r, cy + r + 7 * self.scale * SS],
                                   fill=130 if pal.dark else 90)
        sh = sh.filter(ImageFilter.GaussianBlur(15 * self.scale * SS))
        shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        shadow.putalpha(sh)
        img = Image.alpha_composite(img, shadow)
        # Disco casi invisible (alfa mínimo) para que los huecos entre segmentos reciban el arrastre
        floor = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(floor).ellipse([cx - r, cy - r, cx + r, cy + r], fill=(0, 0, 0, 2))
        img = Image.alpha_composite(img, floor)
        # Vidrio recortado por la unión de segmentos
        union = Image.new("L", (W, H), 0)
        for i in range(self.n):
            union.paste(255, mask=self._segment_mask(i))
        glass = self._glass()
        glass.putalpha(Image.composite(glass.getchannel("A"), Image.new("L", (W, H), 0), union))
        img = Image.alpha_composite(img, glass)
        # Bordes: línea oscura fina + filo claro (da relieve al vidrio)
        rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        rd = ImageDraw.Draw(rim)
        for i in range(self.n):
            a = self.angle_of(i)
            pts = _sector_points(cx, cy, r, self.r_in * SS, a - self.span / 2, a + self.span / 2, GAP * self.scale * SS)
            rd.line(pts + [pts[0]], fill=(0, 0, 0, 70 if pal.dark else 40), width=max(2, int(3 * SS)))
            rd.line(pts + [pts[0]], fill=(255, 255, 255, 105 if pal.dark else 200), width=max(1, int(1.3 * SS)))
        img = Image.alpha_composite(img, rim)
        # Texto
        for i in range(self.n):
            img = Image.alpha_composite(img, self._label_layer(i, pal.text + (255,), shadow=pal.dark))
        self._base = img.resize((self.W, self.H), Image.LANCZOS)
        return self._base

    def hot_layer(self, i: int) -> Image.Image:
        """Segmento activo: resalte del color acento, con brillo y un pequeño 'salto' hacia afuera."""
        if i in self._hot:
            return self._hot[i]
        pal = self.pal
        W, H = self.W * SS, self.H * SS
        r_pop = self.r_out + POP * self.scale
        mask = self._segment_mask(i, r_out=r_pop)
        # resplandor
        glow_mask = mask.filter(ImageFilter.GaussianBlur(10 * self.scale * SS))
        glow = Image.new("RGBA", (W, H), pal.accent + (0,))
        glow.putalpha(glow_mask.point(lambda v: int(v * (0.62 if not pal.neutral_accent else 0.40))))
        # relleno
        top = int((self.cy - r_pop) * SS)
        grad = _vgradient((W, int(r_pop * 2 * SS)), pal.accent_hi, pal.accent_lo, alpha=255)
        fill = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        fill.paste(grad, (0, top))
        fill.putalpha(mask)
        layer = Image.alpha_composite(glow, fill)
        rim = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        a = self.angle_of(i)
        pts = _sector_points(self.cx * SS, self.cy * SS, r_pop * SS, self.r_in * SS,
                             a - self.span / 2, a + self.span / 2, GAP * self.scale * SS)
        ImageDraw.Draw(rim).line(pts + [pts[0]], fill=(255, 255, 255, 140), width=max(1, int(1.6 * SS)))
        layer = Image.alpha_composite(layer, rim)
        layer = Image.alpha_composite(layer, self._label_layer(i, pal.on_accent + (255,), shadow=False))
        self._hot[i] = layer.resize((self.W, self.H), Image.LANCZOS)
        return self._hot[i]

    # --- piezas pequeñas dibujadas a 2x sobre un parche y reducidas
    def _hub_patch(self, text: str, badge: bool, hot: bool):
        pal = self.pal
        r = self.r_in - 5 * self.scale
        size = int(2 * r + 4 * self.scale)
        S = size * SS
        patch = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        c = S / 2
        rr = r * SS
        lighter = tuple(min(255, int(v * 1.5) + 8) for v in pal.tint_deep)
        ring = _vgradient((int(rr * 2), int(rr * 2)), lighter, pal.tint_deep, alpha=246)
        m = Image.new("L", ring.size, 0)
        ImageDraw.Draw(m).ellipse([0, 0, ring.size[0] - 1, ring.size[1] - 1], fill=255)
        ring.putalpha(Image.composite(ring.getchannel("A"), Image.new("L", ring.size, 0), m))
        patch.paste(ring, (int(c - rr), int(c - rr)), ring)
        d = ImageDraw.Draw(patch)
        d.ellipse([c - rr, c - rr, c + rr, c + rr], outline=(255, 255, 255, 90 if pal.dark else 160), width=max(1, int(1.6 * SS)))
        if hot:  # fino aro del color acento cuando hay un segmento activo
            d.ellipse([c - rr + 4 * SS, c - rr + 4 * SS, c + rr - 4 * SS, c + rr - 4 * SS],
                      outline=pal.accent + (200,), width=max(1, int(1.4 * SS)))
        if text:
            fs = int((17 if len(text) <= 6 else 13) * self.scale * SS)
            col = pal.accent if hot else pal.text
            if pal.dark or hot:
                d.text((c, c), text, font=_font(fs), fill=col + (255,), anchor="mm")
            else:
                d.text((c, c), text, font=_font(fs), fill=pal.text + (255,), anchor="mm")
        if badge:
            bx, by = c + rr * 0.62, c + rr * 0.62
            br = 9 * self.scale * SS
            d.ellipse([bx - br, by - br, bx + br, by + br], fill=(52, 178, 86, 255), outline=(255, 255, 255, 220), width=SS)
            d.line([(bx - br * .5, by), (bx + br * .5, by)], fill="white", width=int(2 * SS))
            d.line([(bx, by - br * .5), (bx, by + br * .5)], fill="white", width=int(2 * SS))
        patch = patch.resize((size, size), Image.LANCZOS)
        return patch, (int(self.cx - size / 2), int(self.cy - size / 2))

    def _pill_patch(self, labels: tuple[str, ...], index: int):
        pal = self.pal
        f = _font(int(12 * self.scale * SS))
        probe = ImageDraw.Draw(Image.new("L", (4, 4)))
        gap = 18 * self.scale * SS
        widths = [probe.textlength(t, font=f) + 2 * gap for t in labels]
        total = sum(widths)
        hh = 26 * self.scale * SS
        patch = Image.new("RGBA", (int(total) + 2, int(hh) + 2), (0, 0, 0, 0))
        pd = ImageDraw.Draw(patch)
        pd.rounded_rectangle([0, 0, total, hh], radius=hh / 2, fill=pal.tint_deep + (215,),
                             outline=(255, 255, 255, 70 if pal.dark else 150), width=SS)
        x = 0.0
        for k, t in enumerate(labels):
            if k == index:
                pd.rounded_rectangle([x + 2.5 * SS, 2.5 * SS, x + widths[k] - 2.5 * SS, hh - 2.5 * SS],
                                     radius=hh / 2, fill=pal.accent + (255,))
                pd.text((x + widths[k] / 2, hh / 2), t, font=f, fill=pal.on_accent + (255,), anchor="mm")
            else:
                pd.text((x + widths[k] / 2, hh / 2), t, font=f, fill=pal.text + (205,), anchor="mm")
            x += widths[k]
        w, h = max(1, patch.width // SS), max(1, patch.height // SS)
        patch = patch.resize((w, h), Image.LANCZOS)
        return patch, (int((self.W - w) / 2), int(self.W + 6 * self.scale))

    def render(self, hover=None, center_text: str = "", page_labels: tuple[str, ...] = (), page_index: int = 0,
               copy_badge: bool = False) -> Image.Image:
        """Imagen RGBA final (W x H). `hover`: índice de segmento, 'hub' o None."""
        img = self.base().copy()
        if isinstance(hover, int):
            img = Image.alpha_composite(img, self.hot_layer(hover))
        text = center_text
        if isinstance(hover, int):
            text = _pretty(self.labels[hover]) if self.icons else self.labels[hover]
        hub, pos = self._hub_patch(text, copy_badge and isinstance(hover, int), isinstance(hover, int))
        img.alpha_composite(hub, pos)
        if len(page_labels) > 1:
            pill, ppos = self._pill_patch(page_labels, page_index)
            img.alpha_composite(pill, ppos)
        return img

    def placeholder(self) -> Image.Image:
        """Disco casi invisible (recibe el arrastre) con solo el centro, antes de saber qué archivo es."""
        img = Image.new("RGBA", (self.W, self.H), (0, 0, 0, 0))
        r = self.r_out
        ImageDraw.Draw(img).ellipse([self.cx - r, self.cy - r, self.cx + r, self.cy + r], fill=(0, 0, 0, 2))
        hub, pos = self._hub_patch("···", False, False)
        img.alpha_composite(hub, pos)
        return img


def to_premultiplied_bgra(img: Image.Image) -> bytes:
    """Bytes BGRA con alfa premultiplicado, listos para UpdateLayeredWindow (DIB de 32 bits)."""
    return img.convert("RGBA").tobytes("raw", "BGRa")
