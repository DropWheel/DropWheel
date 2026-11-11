"""Ventanas "Annotate" (lápiz, flecha, formas, texto, resaltador) y "Redact" (tapar zonas en negro)."""
from __future__ import annotations

import tkinter as tk
from tkinter import simpledialog

from ..engine import actions
from ..engine.convert import ConvertError, load_image
from . import theme as T

COLORS = ["#E5484D", "#F5A524", "#FFD60A", "#2FB344", "#2F7DE1", "#8E4EC6", "#111111", "#FFFFFF"]
TOOLS = ["Pen", "Arrow", "Rect", "Ellipse", "Text", "Highlight"]


class AnnotateWindow(T.Window):
    def __init__(self, path: str, redact: bool = False):
        self.path = path
        self.redact = redact
        self.img = load_image(path)
        super().__init__("Redact" if redact else "Annotate", 640, 680)
        self.view = T.ImageView(self.body, self.img, 600, 420)
        self.view.pack(pady=(0, 8))
        self.shapes: list[dict] = []
        self.cur = None
        self.tool = "Rect" if redact else "Pen"
        self.color = COLORS[0]
        self.width = 5

        if not redact:
            tools = tk.Frame(self.body, bg=T.BG)
            tools.pack(fill="x")
            T.ChipRow(tools, TOOLS, self._set_tool, "Pen").pack(side="left")
            cols = tk.Frame(self.body, bg=T.BG)
            cols.pack(fill="x", pady=6)
            for c in COLORS:
                sw = tk.Label(cols, bg=c, width=3, height=1, cursor="hand2", relief="solid", bd=1)
                sw.pack(side="left", padx=2)
                sw.bind("<Button-1>", lambda e, col=c: self._set_color(col))
            T.label(cols, "Grosor", muted=True, size=9).pack(side="left", padx=(14, 4))
            T.scale_slider(cols, 2, 24, 5, lambda v: setattr(self, "width", int(float(v))), 140).pack(side="left")
        else:
            T.label(self.body, "Dibuja rectángulos sobre lo que quieras tapar. Se guardan en negro sólido "
                    "y la copia no conserva metadatos.", muted=True, size=9, wraplength=600, justify="left").pack(anchor="w")

        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(10, 0))
        T.Btn(btns, "Cancelar", self.destroy).pack(side="left")
        T.Btn(btns, "Deshacer", self._undo).pack(side="left", padx=8)
        T.Btn(btns, "Guardar copia", self._save, primary=True).pack(side="right")
        self.status = T.label(self.body, "", muted=True, size=9)
        self.status.pack(anchor="w", pady=(8, 0))

        self.view.bind("<ButtonPress-1>", self._press)
        self.view.bind("<B1-Motion>", self._motion)
        self.view.bind("<ButtonRelease-1>", self._release)
        self.bind("<Control-z>", lambda e: self._undo())

    def _set_tool(self, t):
        self.tool = t

    def _set_color(self, c):
        self.color = c

    def _press(self, e):
        ix, iy = self.view.to_img(e.x, e.y)
        tool = "redact" if self.redact else self.tool.lower()
        if tool == "text":
            txt = simpledialog.askstring("Texto", "Escribe el texto:", parent=self)
            if txt:
                size = int((self.width * 3 + 12) / max(self.view.k, 0.05))
                self.shapes.append({"type": "text", "points": [(ix, iy)], "text": txt, "color": self.color,
                                    "size": size})
                self._redraw()
            return
        self.cur = {"type": tool, "points": [(ix, iy)], "color": "#000000" if self.redact else self.color,
                    "width": max(1, int(self.width / max(self.view.k, 0.05))) if not self.redact else 1}
        self.shapes.append(self.cur)

    def _motion(self, e):
        if not self.cur:
            return
        ix, iy = self.view.to_img(e.x, e.y)
        if self.cur["type"] == "pen":
            self.cur["points"].append((ix, iy))
        else:
            self.cur["points"] = [self.cur["points"][0], (ix, iy)]
        self._redraw()

    def _release(self, e):
        if self.cur and len(self.cur["points"]) < 2 and self.cur["type"] != "pen":
            self.shapes.remove(self.cur)
        self.cur = None
        self._redraw()

    def _undo(self):
        if self.shapes:
            self.shapes.pop()
            self._redraw()

    def _redraw(self):
        c = self.view
        c.delete("ov")
        k = c.k
        for s in self.shapes:
            pts = [(x * k, y * k) for x, y in s["points"]]
            col = s.get("color", "#E5484D")
            wd = max(1, int(s.get("width", 4) * k))
            t = s["type"]
            if t == "pen" and len(pts) > 1:
                c.create_line(*[v for p in pts for v in p], fill=col, width=wd, capstyle="round",
                              joinstyle="round", smooth=True, tags="ov")
            elif t in ("rect", "highlight", "redact") and len(pts) >= 2:
                c.create_rectangle(*pts[0], *pts[-1], outline=col if t == "rect" else "",
                                   fill="black" if t == "redact" else (col if t == "highlight" else ""),
                                   stipple="gray50" if t == "highlight" else "", width=wd, tags="ov")
            elif t == "ellipse" and len(pts) >= 2:
                c.create_oval(*pts[0], *pts[-1], outline=col, width=wd, tags="ov")
            elif t == "arrow" and len(pts) >= 2:
                c.create_line(*pts[0], *pts[-1], fill=col, width=wd, arrow="last", arrowshape=(14, 16, 6), tags="ov")
            elif t == "text":
                c.create_text(*pts[0], text=s["text"], fill=col, anchor="nw",
                              font=T.ui_font(max(8, int(s.get("size", 32) * k * 0.75)), True), tags="ov")

    def _save(self):
        if not self.shapes:
            self.status.configure(text="Todavía no hiciste ningún cambio.", fg=T.ERROR)
            return
        try:
            if self.redact:
                boxes = []
                for s in self.shapes:
                    (x0, y0), (x1, y1) = s["points"][0], s["points"][-1]
                    boxes.append((min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)))
                out = actions.redact_image(self.path, boxes)
            else:
                out = actions.annotate_image(self.path, self.shapes)
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def run(path: str, redact: bool = False):
    win = AnnotateWindow(path, redact)
    win.mainloop()
    return win.result
