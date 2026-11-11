"""Ventana "Edit": rotar, voltear, brillo/contraste/saturación/nitidez, blanco y negro, tamaño."""
from __future__ import annotations

import tkinter as tk

from PIL import Image, ImageTk

from ..engine import actions
from ..engine.convert import ConvertError, load_image
from . import theme as T


class EditWindow(T.Window):
    def __init__(self, path: str):
        self.path = path
        self.img = load_image(path)
        super().__init__("Edit", 600, 720)
        self.small = self.img.copy()
        self.small.thumbnail((720, 720))
        self.p = dict(rotate=0, flip_h=False, flip_v=False, brightness=1.0, contrast=1.0, saturation=1.0,
                      sharpness=1.0, grayscale=False, blur=0.0, resize_pct=100)

        self.preview = tk.Label(self.body, bg=T.PREVIEW_BG)
        self.preview.pack(pady=(0, 8))

        row = tk.Frame(self.body, bg=T.BG)
        row.pack(fill="x", pady=(0, 6))
        T.Btn(row, "⟲ 90°", lambda: self._rot(-90)).pack(side="left", padx=(0, 6))
        T.Btn(row, "⟳ 90°", lambda: self._rot(90)).pack(side="left", padx=(0, 6))
        T.Btn(row, "↔ Voltear", lambda: self._toggle("flip_h")).pack(side="left", padx=(0, 6))
        T.Btn(row, "↕ Voltear", lambda: self._toggle("flip_v")).pack(side="left", padx=(0, 6))
        T.Btn(row, "B/N", lambda: self._toggle("grayscale")).pack(side="left")

        grid = tk.Frame(self.body, bg=T.BG)
        grid.pack(fill="x")
        defs = [("Brillo", "brightness", 20, 180, 100, 100), ("Contraste", "contrast", 20, 180, 100, 100),
                ("Saturación", "saturation", 0, 200, 100, 100), ("Nitidez", "sharpness", 0, 300, 100, 100),
                ("Desenfoque", "blur", 0, 100, 0, 10), ("Tamaño %", "resize_pct", 10, 200, 100, 1)]
        for i, (title, key, lo, hi, val, div) in enumerate(defs):
            cell = tk.Frame(grid, bg=T.BG)
            cell.grid(row=i // 2, column=i % 2, padx=8, pady=2, sticky="w")
            T.label(cell, title, muted=True, size=9).pack(anchor="w")
            T.scale_slider(cell, lo, hi, val, lambda v, k=key, d=div: self._slider(k, float(v) / d), 240).pack()

        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(10, 0))
        T.Btn(btns, "Cancelar", self.destroy).pack(side="left")
        T.Btn(btns, "Guardar copia", self._save, primary=True).pack(side="right")
        self.status = T.label(self.body, "", muted=True, size=9)
        self.status.pack(anchor="w", pady=(8, 0))
        self._render()

    def _rot(self, d):
        self.p["rotate"] = (self.p["rotate"] + d) % 360
        self._render()

    def _toggle(self, k):
        self.p[k] = not self.p[k]
        self._render()

    def _slider(self, k, v):
        self.p[k] = int(v) if k == "resize_pct" else v
        self._render()

    def _render(self):
        out = actions.apply_edits(self.small, **self.p)
        out = out.copy()
        out.thumbnail((540, 330))
        chk = Image.new("RGBA", out.size, (235, 235, 235, 255))
        self._ph = ImageTk.PhotoImage(Image.alpha_composite(chk, out.convert("RGBA")))
        self.preview.configure(image=self._ph)

    def _save(self):
        try:
            out = actions.save_like(self.path, actions.apply_edits(self.img, **self.p), " Edited")
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def run(path: str):
    win = EditWindow(path)
    win.mainloop()
    return win.result
