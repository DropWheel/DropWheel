"""Humo de las ventanas tkinter: las abre, simula uso y guarda capturas. Requiere pantalla (xvfb-run)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PIL import Image, ImageDraw, ImageGrab

OUT = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp()
td = tempfile.mkdtemp()
src = os.path.join(td, "Page 001.jpg")
im = Image.new("RGB", (1600, 1100), (250, 250, 250))
d = ImageDraw.Draw(im)
for i in range(30):
    d.text((80, 60 + i * 30), "Linea de texto de ejemplo %d  Lorem ipsum dolor sit amet" % i, fill=(20, 20, 20))
d.rectangle([60, 40, 1540, 1060], outline=(180, 30, 30), width=5)
im.save(src, exif=Image.Exif())

def shot(win, name):
    win.update()
    win.update_idletasks()
    x, y, w, h = win.winfo_rootx(), win.winfo_rooty(), win.winfo_width(), win.winfo_height()
    ImageGrab.grab(bbox=(x, y, x + w, y + h)).save(os.path.join(OUT, name + ".png"))

def close(w):
    try:
        w.destroy()
    except Exception:
        pass

class E:  # evento falso
    def __init__(self, x, y): self.x, self.y = x, y

results = {}
# --- Crop
from dropwheel.ui import crop
w = crop.CropWindow(src)
w.update(); v = w.view
w._press(E(40, 40)); w._motion(E(300, 220)); w._release = None; w.drag = None
w.chips.select("16:9")
shot(w, "crop")
w.w_var.set("800"); w._dims_entered()
w._apply(); results["crop"] = w.result; close(w)
# --- Add BG
from dropwheel.ui import addbg
w = addbg.AddBgWindow(src); w.update()
w._set_ratio("16:9"); shot(w, "addbg"); w._save(); results["addbg"] = w.result; close(w)
# --- Edit
from dropwheel.ui import editor
w = editor.EditWindow(src); w.update()
w._rot(90); w._slider("contrast", 1.3); shot(w, "edit"); w._save(); results["edit"] = w.result; close(w)
# --- Annotate / Redact
from dropwheel.ui import annotate
w = annotate.AnnotateWindow(src); w.update()
w.tool = "Rect"; w._press(E(60, 60)); w._motion(E(260, 140)); w._release(E(260, 140))
w.tool = "Arrow"; w._press(E(300, 300)); w._motion(E(420, 360)); w._release(E(420, 360))
w.tool = "Pen"; w._press(E(100, 200)); [w._motion(E(100 + i * 8, 200 + (i % 5) * 6)) for i in range(20)]; w._release(E(0, 0))
w.tool = "Highlight"; w._press(E(60, 250)); w._motion(E(380, 290)); w._release(E(380, 290))
shot(w, "annotate"); w._save(); results["annotate"] = w.result; close(w)
w = annotate.AnnotateWindow(src, redact=True); w.update()
w._press(E(60, 60)); w._motion(E(260, 140)); w._release(E(260, 140))
shot(w, "redact"); w._save(); results["redact"] = w.result; close(w)
# --- Compress
from dropwheel.ui import compress
w = compress.CompressWindow(src); w.update(); w._q(40); shot(w, "compress"); w._save(); results["compress"] = w.result; close(w)
# --- Metadata
from dropwheel.ui import metadata
w = metadata.MetadataWindow(src); w.update(); shot(w, "metadata"); w._clean(); results["metadata"] = w.result; close(w)
for k, v in results.items():
    assert v and os.path.exists(v), (k, v)
    print(k, "->", os.path.basename(v), os.path.getsize(v), "bytes")
print("UI OK")
