"""Estilo compartido de las ventanas (durazno/naranja, como la rueda). Solo tkinter + Pillow."""
from __future__ import annotations

import sys
import tkinter as tk
from tkinter import font as tkfont

from PIL import Image, ImageTk

BG = CARD = ACCENT = ACCENT_HOVER = TEXT = MUTED = LINE = CHIP = ON_ACCENT = ERROR = PREVIEW_BG = ""
HEAD_A = HEAD_B = (0, 0, 0)


def _hex(c) -> str:
    return "#%02x%02x%02x" % tuple(c)


def apply_palette(pal) -> None:
    """Colores de TODAS las ventanas a partir de la paleta de la rueda (color dominante del fondo)."""
    global BG, CARD, ACCENT, ACCENT_HOVER, TEXT, MUTED, LINE, CHIP, ON_ACCENT, ERROR, PREVIEW_BG, HEAD_A, HEAD_B
    from ..colors import mix

    white, black = (255, 255, 255), (0, 0, 0)
    if pal.dark:
        bg = pal.tint
        card, chip, line = mix(bg, white, 0.07), mix(bg, white, 0.11), mix(bg, white, 0.18)
        err, prev = "#FF7A6E", mix(bg, black, 0.5)
        head_a = mix(bg, white, 0.07)
    else:
        bg = pal.tint
        card, chip, line = mix(bg, white, 0.6), mix(bg, black, 0.06), mix(bg, black, 0.14)
        err, prev = "#C0261A", mix(bg, black, 0.78)
        head_a = mix(bg, white, 0.5)
    BG, CARD, CHIP, LINE = _hex(bg), _hex(card), _hex(chip), _hex(line)
    TEXT = _hex(pal.text)
    MUTED = _hex(pal.muted if pal.dark else mix(pal.text, bg, 0.4))
    ACCENT = _hex(pal.accent)
    ACCENT_HOVER = _hex(pal.accent_lo if pal.dark else pal.accent_hi)
    ON_ACCENT = _hex(pal.on_accent)
    ERROR, PREVIEW_BG = err, _hex(prev)
    HEAD_A = head_a
    HEAD_B = mix(bg, pal.accent, 0.38 if not pal.neutral_accent else 0.12)


def _init_palette() -> None:
    from .. import colors

    apply_palette(colors.from_env() or colors.wallpaper_palette())


_init_palette()


def init_dpi() -> None:
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:  # noqa: BLE001
            pass


def ui_font(size=10, bold=False):
    fam = "Segoe UI" if sys.platform == "win32" else "DejaVu Sans"
    return (fam, size, "bold" if bold else "normal")


def gradient(w: int, h: int, a, b, horizontal=False) -> Image.Image:
    n = w if horizontal else h
    strip = Image.new("RGB", (max(1, n), 1))
    for i in range(n):
        t = i / max(1, n - 1)
        strip.putpixel((i, 0), tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3)))
    if not horizontal:
        strip = strip.transpose(Image.Transpose.TRANSPOSE)
    return strip.resize((w, h))


class Window(tk.Tk):
    """Ventana con cabecera degradada y cuerpo durazno."""

    def __init__(self, title: str, width: int, height: int):
        init_dpi()
        super().__init__()
        self.title(title)
        self.configure(bg=BG)
        self.resizable(False, False)
        self.result = None
        self._hdr_img = ImageTk.PhotoImage(gradient(width, 46, HEAD_A, HEAD_B, horizontal=True))
        hdr = tk.Canvas(self, width=width, height=46, highlightthickness=0, bd=0)
        hdr.pack(fill="x")
        hdr.create_image(0, 0, image=self._hdr_img, anchor="nw")
        hdr.create_text(width // 2, 23, text=title, fill=TEXT, font=ui_font(12, True))
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True, padx=14, pady=12)
        sw, sh = self.winfo_screenwidth(), self.winfo_screenheight()
        self.geometry(f"{width}x{height}+{(sw - width) // 2}+{max(20, (sh - height) // 3)}")
        self.attributes("-topmost", True)
        self.after(300, self._untop)
        self.bind("<Escape>", lambda e: self.destroy())

    def _untop(self) -> None:
        try:
            self.attributes("-topmost", False)
        except tk.TclError:
            pass

    def finish(self, result) -> None:
        self.result = result
        self.destroy()


class Btn(tk.Label):
    def __init__(self, master, text, command, primary=False, width=None, **kw):
        self.primary = primary
        self._cmd = command
        bg = ACCENT if primary else CHIP
        super().__init__(master, text=text, bg=bg, fg=ON_ACCENT if primary else TEXT, font=ui_font(10, True),
                         padx=16, pady=7, cursor="hand2", width=width or 0, **kw)
        self._bg = bg
        self.bind("<Enter>", lambda e: self.configure(bg=ACCENT_HOVER if primary else LINE))
        self.bind("<Leave>", lambda e: self.configure(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())


class ChipRow(tk.Frame):
    """Fila de opciones tipo 'chip' (una activa a la vez)."""

    def __init__(self, master, options, on_change, initial=None, bg=BG):
        super().__init__(master, bg=bg)
        self.on_change = on_change
        self.chips: dict[str, tk.Label] = {}
        self.value = initial if initial is not None else options[0]
        for opt in options:
            lab = tk.Label(self, text=opt, font=ui_font(9, True), padx=10, pady=4, cursor="hand2")
            lab.pack(side="left", padx=2)
            lab.bind("<Button-1>", lambda e, o=opt: self.select(o))
            self.chips[opt] = lab
        self._paint()

    def select(self, opt: str, notify=True) -> None:
        self.value = opt
        self._paint()
        if notify:
            self.on_change(opt)

    def _paint(self) -> None:
        for o, lab in self.chips.items():
            on = o == self.value
            lab.configure(bg=ACCENT if on else CHIP, fg=ON_ACCENT if on else TEXT)


def label(master, text, muted=False, size=10, bold=False, **kw):
    return tk.Label(master, text=text, bg=kw.pop("bg", BG), fg=MUTED if muted else TEXT, font=ui_font(size, bold), **kw)


def scale_slider(master, from_, to, value, command, length=220):
    s = tk.Scale(master, from_=from_, to=to, orient="horizontal", showvalue=True, length=length, command=command,
                 bg=BG, fg=TEXT, troughcolor=LINE, highlightthickness=0, bd=0, activebackground=ACCENT,
                 font=ui_font(9), sliderrelief="flat")
    s.set(value)
    return s


class ImageView(tk.Canvas):
    """Canvas que muestra una imagen PIL ajustada al espacio disponible."""

    def __init__(self, master, img: Image.Image, max_w: int, max_h: int, bg=None):
        self.max_w, self.max_h = max_w, max_h
        self.img = img
        k = min(max_w / img.width, max_h / img.height, 1.0)
        self.k = k
        w, h = max(1, int(img.width * k)), max(1, int(img.height * k))
        super().__init__(master, width=w, height=h, highlightthickness=0, bd=0, bg=bg or PREVIEW_BG, cursor="crosshair")
        self.disp_w, self.disp_h = w, h
        self.set_image(img)

    def set_image(self, img: Image.Image) -> None:
        self.img = img
        prev = img.convert("RGBA").resize((self.disp_w, self.disp_h), Image.LANCZOS)
        # tablero para ver transparencia
        chk = Image.new("RGBA", prev.size, (235, 235, 235, 255))
        from PIL import ImageDraw

        d = ImageDraw.Draw(chk)
        for yy in range(0, prev.height, 12):
            for xx in range(0, prev.width, 12):
                if (xx // 12 + yy // 12) % 2:
                    d.rectangle([xx, yy, xx + 11, yy + 11], fill=(205, 205, 205, 255))
        self._photo = ImageTk.PhotoImage(Image.alpha_composite(chk, prev))
        self.delete("base")
        self.create_image(0, 0, image=self._photo, anchor="nw", tags="base")
        self.tag_lower("base")

    def to_img(self, cx, cy):
        return cx / self.k, cy / self.k

    def to_canvas(self, ix, iy):
        return ix * self.k, iy * self.k
