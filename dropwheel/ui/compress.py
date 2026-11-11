"""Ventana "Compress": calidad y tamaño máximo con estimación del peso resultante."""
from __future__ import annotations

import os
import tkinter as tk

from ..catalog import human_size, kind_of
from ..engine import actions
from ..engine.convert import ConvertError, load_image
from . import theme as T

SIDES = {"Original": None, "4096": 4096, "2048": 2048, "1280": 1280, "800": 800}


class CompressWindow(T.Window):
    def __init__(self, path: str):
        self.path = path
        self.is_pdf = kind_of(path) == "pdf"
        super().__init__("Compress", 480, 360 if self.is_pdf else 430)
        self.quality = 70
        self.max_side = None
        self.orig = os.path.getsize(path)
        T.label(self.body, f"Original: {human_size(path)}", size=11, bold=True).pack(anchor="w")
        self.est = T.label(self.body, "", muted=True, size=10)
        self.est.pack(anchor="w", pady=(2, 10))
        T.label(self.body, "Calidad (más bajo = pesa menos)", muted=True, size=9).pack(anchor="w")
        T.scale_slider(self.body, 10, 100, 70, self._q, 380).pack(anchor="w")
        if not self.is_pdf:
            self.img = load_image(path)
            T.label(self.body, "Lado máximo (px)", muted=True, size=9).pack(anchor="w", pady=(8, 2))
            T.ChipRow(self.body, list(SIDES), self._side, "Original").pack(anchor="w")
        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(16, 0))
        T.Btn(btns, "Cancelar", self.destroy).pack(side="left")
        T.Btn(btns, "Comprimir", self._save, primary=True).pack(side="right")
        self.status = T.label(self.body, "", muted=True, size=9)
        self.status.pack(anchor="w", pady=(8, 0))
        self._estimate()

    def _q(self, v):
        self.quality = int(float(v))
        self._estimate()

    def _side(self, name):
        self.max_side = SIDES[name]
        self._estimate()

    def _estimate(self):
        if self.is_pdf:
            self.est.configure(text="El tamaño final depende de las imágenes que tenga el PDF.")
            return
        try:
            n = actions.estimate_compress(self.path, self.quality, self.max_side, img=self.img)
        except Exception:  # noqa: BLE001
            return
        pct = 100 - int(100 * n / max(1, self.orig))
        self.est.configure(text=f"Estimado: ~{n / 1024 / 1024:.2f} MB" if n > 1024 * 1024 else f"Estimado: ~{n / 1024:.0f} KB"
                           + (f"  ({pct}% menos)" if pct > 0 else "  (sin ganancia)"))

    def _save(self):
        try:
            if self.is_pdf:
                out = actions.compress_pdf(self.path, image_quality=self.quality)
            else:
                out = actions.compress_image(self.path, self.quality, self.max_side)
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def run(path: str):
    win = CompressWindow(path)
    win.mainloop()
    return win.result
