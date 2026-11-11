"""Ventana "Add BG": coloca la imagen sobre un fondo (color, degradado o transparente)."""
from __future__ import annotations

import tkinter as tk
from tkinter import colorchooser

from PIL import Image, ImageTk

from ..engine import actions
from ..engine.convert import ConvertError, load_image
from . import theme as T

RATIOS = {"Auto": None, "1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3), "3:4": (3, 4)}


class AddBgWindow(T.Window):
    def __init__(self, path: str):
        self.path = path
        self.img = load_image(path)
        super().__init__("Add BG", 600, 720)
        self.spec = actions.BG_PRESETS["Atardecer"]
        self.aspect = None
        self.small = self.img.copy()
        self.small.thumbnail((700, 700))

        self.preview = tk.Label(self.body, bg=T.PREVIEW_BG)
        self.preview.pack(pady=(0, 10))

        T.label(self.body, "Background", muted=True, size=9).pack(anchor="w")
        sw = tk.Frame(self.body, bg=T.BG)
        sw.pack(fill="x", pady=(2, 8))
        self._sw_imgs = []
        for i, (name, spec) in enumerate(actions.BG_PRESETS.items()):
            im = self._swatch(spec)
            ph = ImageTk.PhotoImage(im)
            self._sw_imgs.append(ph)
            b = tk.Label(sw, image=ph, bd=2, relief="flat", cursor="hand2", bg=T.BG)
            b.grid(row=i // 9, column=i % 9, padx=2, pady=2)
            b.bind("<Button-1>", lambda e, s=spec: self._set_spec(s))
        pick = T.Btn(self.body, "Color personalizado…", self._pick_color)
        pick.pack(anchor="w", pady=(0, 8))

        self.pad = tk.IntVar(value=12)
        self.rad = tk.IntVar(value=3)
        self.shadow = tk.BooleanVar(value=True)
        row = tk.Frame(self.body, bg=T.BG)
        row.pack(fill="x")
        left = tk.Frame(row, bg=T.BG)
        left.pack(side="left")
        T.label(left, "Padding", muted=True, size=9).pack(anchor="w")
        T.scale_slider(left, 0, 40, 12, lambda v: self._on_slider("pad", v), 200).pack()
        mid = tk.Frame(row, bg=T.BG)
        mid.pack(side="left", padx=18)
        T.label(mid, "Corner radius", muted=True, size=9).pack(anchor="w")
        T.scale_slider(mid, 0, 15, 3, lambda v: self._on_slider("rad", v), 200).pack()

        ar = tk.Frame(self.body, bg=T.BG)
        ar.pack(fill="x", pady=8)
        T.label(ar, "Aspect ratio", muted=True, size=9).pack(side="left", padx=(0, 8))
        T.ChipRow(ar, list(RATIOS), self._set_ratio, "Auto").pack(side="left")
        tk.Checkbutton(ar, text="Shadow", variable=self.shadow, command=self._render, bg=T.BG, fg=T.TEXT,
                       activebackground=T.BG, font=T.ui_font(9, True), selectcolor=T.CARD).pack(side="right")

        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(8, 0))
        T.Btn(btns, "Cancelar", self.destroy).pack(side="left")
        T.Btn(btns, "Guardar", self._save, primary=True).pack(side="right")
        self.status = T.label(self.body, "", muted=True, size=9)
        self.status.pack(anchor="w", pady=(8, 0))
        self._render()

    def _swatch(self, spec):
        s = 34
        if spec[0] == "solid":
            return Image.new("RGB", (s, s), spec[1])
        if spec[0] == "gradient":
            return T.gradient(s, s, _rgb(spec[1]), _rgb(spec[2]))
        im = Image.new("RGB", (s, s), (240, 240, 240))
        from PIL import ImageDraw

        d = ImageDraw.Draw(im)
        for yy in range(0, s, 8):
            for xx in range(0, s, 8):
                if (xx // 8 + yy // 8) % 2:
                    d.rectangle([xx, yy, xx + 7, yy + 7], fill=(200, 200, 200))
        return im

    def _set_spec(self, spec):
        self.spec = spec
        self._render()

    def _pick_color(self):
        c = colorchooser.askcolor(parent=self)[1]
        if c:
            self._set_spec(("solid", c))

    def _set_ratio(self, name):
        self.aspect = RATIOS[name]
        self._render()

    def _on_slider(self, which, v):
        getattr(self, which).set(int(float(v)))
        self._render()

    def _opts(self):
        return dict(padding_pct=self.pad.get(), radius_pct=self.rad.get(), shadow=self.shadow.get(),
                    aspect=self.aspect)

    def _render(self):
        out = actions.add_background(self.small, self.spec, **self._opts())
        out.thumbnail((540, 330))
        chk = Image.new("RGBA", out.size, (235, 235, 235, 255))
        self._ph = ImageTk.PhotoImage(Image.alpha_composite(chk, out))
        self.preview.configure(image=self._ph)

    def _save(self):
        try:
            out = actions.add_background_file(self.path, self.spec, **self._opts())
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def run(path: str):
    win = AddBgWindow(path)
    win.mainloop()
    return win.result
