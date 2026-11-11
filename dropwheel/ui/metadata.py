"""Ventana "Metadata": muestra los metadatos y permite guardar una copia limpia."""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..engine import actions
from ..engine.convert import ConvertError
from . import theme as T


class MetadataWindow(T.Window):
    def __init__(self, path: str):
        self.path = path
        super().__init__("Metadata", 600, 560)
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Treeview", background=T.CARD, fieldbackground=T.CARD, foreground=T.TEXT, rowheight=24,
                        borderwidth=0, font=T.ui_font(9))
        style.configure("Treeview.Heading", background=T.CHIP, foreground=T.TEXT, font=T.ui_font(9, True))
        style.map("Treeview", background=[("selected", T.ACCENT)], foreground=[("selected", "white")])
        wrap = tk.Frame(self.body, bg=T.BG)
        wrap.pack(fill="both", expand=True)
        tree = ttk.Treeview(wrap, columns=("v",), show="tree headings", height=17)
        tree.heading("#0", text="Campo")
        tree.heading("v", text="Valor")
        tree.column("#0", width=210)
        tree.column("v", width=330)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=sb.set)
        tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        try:
            sections = actions.read_metadata(path)
        except Exception as e:  # noqa: BLE001
            sections = [("Error", [("No pude leer", str(e))])]
        self.has_private = False
        for title, rows in sections:
            node = tree.insert("", "end", text=title, open=True)
            for k, v in rows:
                tree.insert(node, "end", text=k, values=(v,))
            if title.startswith("GPS"):
                self.has_private = True
        btns = tk.Frame(self.body, bg=T.BG)
        btns.pack(fill="x", pady=(10, 0))
        T.Btn(btns, "Cerrar", self.destroy).pack(side="left")
        T.Btn(btns, "Guardar copia sin metadatos", self._clean, primary=True).pack(side="right")
        msg = "Esta imagen incluye ubicación (GPS)." if self.has_private else ""
        self.status = T.label(self.body, msg, muted=not msg, size=9)
        if msg:
            self.status.configure(fg=T.ERROR)
        self.status.pack(anchor="w", pady=(8, 0))

    def _clean(self):
        try:
            out = actions.strip_metadata(self.path)
        except ConvertError as e:
            self.status.configure(text=str(e), fg=T.ERROR)
            return
        self.finish(out)


def run(path: str):
    win = MetadataWindow(path)
    win.mainloop()
    return win.result
