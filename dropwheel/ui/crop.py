"""Ventana "Crop Image": recorte con proporciones (Free, 1:1, 16:9, 9:16, 4:3, 3:4) y medidas en px."""
from __future__ import annotations

import tkinter as tk

from ..engine import actions
from ..engine.convert import ConvertError, load_image
from . import theme as T

ASPECTS = {"Free": None, "1:1": (1, 1), "16:9": (16, 9), "9:16": (9, 16), "4:3": (4, 3), "3:4": (3, 4)}
HANDLE = 7


class CropWindow(T.Window):
    def __init__(self, path: str):
        self.path = path
        self.img = load_image(path)
        super().__init__("Crop Image", 560, 640)
        self.view = T.ImageView(self.body, self.img, 520, 400)
        self.view.pack(pady=(0, 10))
        W, H = self.img.size
        self.box = [0.0, 0.0, float(W), float(H)]
        self.aspect = None
        self.drag = None

        row = tk.Frame(self.body, bg=T.BG)
        row.pack(fill="x")
        T.label(row, "Aspect ratio", muted=True, size=9).pack(side="left", padx=(0, 8))
        self.chips = T.ChipRow(row, list(ASPECTS), self._set_aspect, "Free")
        self.chips.pack(side="left")

        dims = tk.Frame(self.body, bg=T.BG)
        dims.pack(fill="x", pady=10)
        self.w_var, self.h_var = tk.StringVar(), tk.StringVar()
        T.label(dims, "W", muted=True, size=9).pack(side="left")
        we = tk.Entry(dims, textvariable=self.w_var, width=7, justify="center", relief="flat", bg=T.CARD, fg=T.TEXT)
        we.pack(side="left", padx=(4, 12), ipady=4)
        T.label(dims, "H", muted=True, size=9).pack(side="left")
        he = tk.Entry(dims, textvariable=self.h_var, width=7, justify="center", relief="flat", bg=T.CARD, fg=T.TEXT)
        he.pack(side="left", padx=(4, 4), ipady=4)
        T.label(dims, "px", muted=True, size=9).pack(side="left")
        for e in (we, he):
            e.bind("<Return>", lambda ev: self._dims_entered())
            e.bind("<FocusOut>", lambda ev: self._dims_entered())

        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(6, 0))
        T.Btn(btns, "Reset", self._reset).pack(side="left")
        T.Btn(btns, "Apply", self._apply, primary=True).pack(side="right")
        self.status = T.label(self.body, "Arrastra para dibujar el recorte; usa las esquinas para ajustar.",
                              muted=True, size=9)
        self.status.pack(anchor="w", pady=(10, 0))

        self.view.bind("<ButtonPress-1>", self._press)
        self.view.bind("<B1-Motion>", self._motion)
        self.view.bind("<ButtonRelease-1>", lambda e: setattr(self, "drag", None))
        self.view.bind("<Motion>", self._cursor)
        self._redraw()

    # ---- geometría
    def _handles(self):
        l, t, r, b = self.box
        mx, my = (l + r) / 2, (t + b) / 2
        return {"nw": (l, t), "n": (mx, t), "ne": (r, t), "w": (l, my), "e": (r, my),
                "sw": (l, b), "s": (mx, b), "se": (r, b)}

    def _hit(self, cx, cy):
        for name, (ix, iy) in self._handles().items():
            hx, hy = self.view.to_canvas(ix, iy)
            if abs(cx - hx) <= HANDLE + 3 and abs(cy - hy) <= HANDLE + 3:
                return name
        l, t, r, b = [v * self.view.k for v in self.box]
        if l <= cx <= r and t <= cy <= b:
            return "move"
        return None

    def _clamp(self):
        W, H = self.img.size
        l, t, r, b = self.box
        l, r = sorted((max(0, min(W, l)), max(0, min(W, r))))
        t, b = sorted((max(0, min(H, t)), max(0, min(H, b))))
        self.box = [l, t, r, b]

    def _cursor(self, e):
        h = self._hit(e.x, e.y)
        cur = {"nw": "top_left_corner", "se": "bottom_right_corner", "ne": "top_right_corner",
               "sw": "bottom_left_corner", "n": "sb_v_double_arrow", "s": "sb_v_double_arrow",
               "w": "sb_h_double_arrow", "e": "sb_h_double_arrow", "move": "fleur"}.get(h, "crosshair")
        self.view.configure(cursor=cur)

    def _press(self, e):
        h = self._hit(e.x, e.y)
        ix, iy = self.view.to_img(e.x, e.y)
        if h is None:
            self.drag = ("new", ix, iy)
            self.box = [ix, iy, ix, iy]
        elif h == "move":
            self.drag = ("move", ix, iy, list(self.box))
        else:
            self.drag = ("resize", h)

    def _motion(self, e):
        if not self.drag:
            return
        ix, iy = self.view.to_img(e.x, e.y)
        W, H = self.img.size
        ix, iy = max(0, min(W, ix)), max(0, min(H, iy))
        kind = self.drag[0]
        if kind == "new":
            _, x0, y0 = self.drag
            self.box = [min(x0, ix), min(y0, iy), max(x0, ix), max(y0, iy)]
            if self.aspect:
                self._fit_aspect(anchor=(x0, y0), pointer=(ix, iy))
        elif kind == "move":
            _, x0, y0, b0 = self.drag
            dx, dy = ix - x0, iy - y0
            w, h = b0[2] - b0[0], b0[3] - b0[1]
            l = max(0, min(W - w, b0[0] + dx))
            t = max(0, min(H - h, b0[1] + dy))
            self.box = [l, t, l + w, t + h]
        else:
            self._resize(self.drag[1], ix, iy)
        self._clamp()
        self._redraw()

    def _fit_aspect(self, anchor, pointer):
        ar = self.aspect[0] / self.aspect[1]
        ax, ay = anchor
        px, py = pointer
        w, h = abs(px - ax), abs(py - ay)
        if h == 0 or w / max(h, 1e-6) > ar:
            w = h * ar
        else:
            h = w / ar
        W, H = self.img.size
        sx = 1 if px >= ax else -1
        sy = 1 if py >= ay else -1
        x1, y1 = ax + sx * w, ay + sy * h
        x1, y1 = max(0, min(W, x1)), max(0, min(H, y1))
        self.box = [min(ax, x1), min(ay, y1), max(ax, x1), max(ay, y1)]

    def _resize(self, handle, ix, iy):
        l, t, r, b = self.box
        if "w" in handle:
            l = min(ix, r - 4)
        if "e" in handle:
            r = max(ix, l + 4)
        if "n" in handle:
            t = min(iy, b - 4)
        if "s" in handle:
            b = max(iy, t + 4)
        self.box = [l, t, r, b]
        if self.aspect:
            ar = self.aspect[0] / self.aspect[1]
            w, h = r - l, b - t
            if handle in ("n", "s"):
                w = h * ar
                cx = (l + r) / 2
                self.box = [cx - w / 2, t, cx + w / 2, b]
            elif handle in ("e", "w"):
                h = w / ar
                cy = (t + b) / 2
                self.box = [l, cy - h / 2, r, cy + h / 2]
            else:
                h = w / ar
                if "n" in handle:
                    self.box[1] = b - h
                else:
                    self.box[3] = t + h

    def _set_aspect(self, name):
        self.aspect = ASPECTS[name]
        if self.aspect:
            W, H = self.img.size
            ar = self.aspect[0] / self.aspect[1]
            l, t, r, b = self.box
            w, h = r - l, b - t
            if w < 8 or h < 8:
                w, h, l, t = W, H, 0, 0
            cx, cy = l + w / 2, t + h / 2
            if w / h > ar:
                w = h * ar
            else:
                h = w / ar
            self.box = [cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2]
            self._shift_inside()
        self._redraw()

    def _shift_inside(self):
        W, H = self.img.size
        l, t, r, b = self.box
        dx = -l if l < 0 else (W - r if r > W else 0)
        dy = -t if t < 0 else (H - b if b > H else 0)
        self.box = [l + dx, t + dy, r + dx, b + dy]
        self._clamp()

    def _dims_entered(self):
        try:
            w, h = int(float(self.w_var.get())), int(float(self.h_var.get()))
        except ValueError:
            self._update_dims()
            return
        W, H = self.img.size
        l, t = self.box[0], self.box[1]
        w, h = max(1, min(W, w)), max(1, min(H, h))
        if self.aspect and abs(self.box[2] - self.box[0] - w) > 0.5:  # cambió el ancho: ajustar alto
            h = max(1, min(H, int(round(w * self.aspect[1] / self.aspect[0]))))
        self.box = [l, t, l + w, t + h]
        self._shift_inside()
        self._redraw()

    def _reset(self):
        W, H = self.img.size
        self.box = [0.0, 0.0, float(W), float(H)]
        self.chips.select("Free")
        self._redraw()

    def _update_dims(self):
        self.w_var.set(str(int(round(self.box[2] - self.box[0]))))
        self.h_var.set(str(int(round(self.box[3] - self.box[1]))))

    def _redraw(self):
        c = self.view
        c.delete("ov")
        k = c.k
        l, t, r, b = [v * k for v in self.box]
        W, H = c.disp_w, c.disp_h
        for rect in ((0, 0, W, t), (0, b, W, H), (0, t, l, b), (r, t, W, b)):
            c.create_rectangle(*rect, fill="black", stipple="gray50", outline="", tags="ov")
        c.create_rectangle(l, t, r, b, outline=T.ACCENT, width=2, tags="ov")
        for name, (ix, iy) in self._handles().items():
            hx, hy = c.to_canvas(ix, iy)
            c.create_rectangle(hx - HANDLE / 2, hy - HANDLE / 2, hx + HANDLE / 2, hy + HANDLE / 2,
                               fill=T.ACCENT, outline="white", tags="ov")
        self._update_dims()

    def _apply(self):
        l, t, r, b = self.box
        try:
            out = actions.crop_image(self.path, (l, t, r, b), img=self.img)
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def run(path: str):
    win = CropWindow(path)
    win.mainloop()
    return win.result
