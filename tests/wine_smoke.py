"""Prueba de la capa Win32 REAL (ventana con alfa por píxel, captura de pantalla, IDropTarget) ejecutada con el
Python de Windows bajo Wine. En Windows de verdad también sirve: python tests\\wine_smoke.py"""
import ctypes, os, sys, time
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from ctypes import wintypes as wt
from dropwheel import colors, win32 as w
from dropwheel.droptarget import DropTarget
from dropwheel.overlay import LayeredWindow
from dropwheel.screencap import capture_region
from dropwheel.wheelgfx import Wheel, to_premultiplied_bgra

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
w.set_dpi_aware()
print("OleInitialize ->", w.OleInitialize(None))
print("scale", w.system_dpi_scale())
win = LayeredWindow(lambda h, m, wp, lp: w.DefWindowProcW(h, m, wp, lp))
print("hwnd", bool(win.hwnd))
cap = capture_region(0, 0, 360, 394)
print("capture", cap.size if cap else None)
pal = colors.from_image(cap) if cap else colors.default_palette()
wheel = Wheel(["PNG", "JPG", "WEBP", "PDF", "DOCX"], 0.85, False, pal, cap)
img = wheel.render(hover=1, center_text="1.2 MB", page_labels=("Convertir", "Acciones"), copy_badge=True)
win.update(to_premultiplied_bgra(img), wheel.W, wheel.H, 500, 250)
win.show(); win.set_alpha(200); win.set_alpha(255)
print("layered window shown", win.visible)

events = []
dt = DropTarget(win.hwnd, lambda p, x, y: events.append(("enter", p, x, y)) or True,
                lambda x, y: events.append(("over", x, y)) or 1,
                lambda: events.append(("leave",)),
                lambda x, y: events.append(("drop", x, y)) or 1)
dt.register()
print("RegisterDragDrop ok")

# Llamar al vtable como lo haría OLE (verifica firmas, empaquetado de POINTL y efectos)
this = ctypes.addressof(dt._obj)
eff = wt.DWORD(0)
pt = (123 & 0xFFFFFFFF) | (456 << 32)
print("DragOver hr", dt._vtbl.DragOver(this, 0, pt, ctypes.byref(eff)), "effect", eff.value, "(sin enter: 0)")
iid = (ctypes.c_ubyte * 16)(*w.GUID.from_string("00000122-0000-0000-C000-000000000046").bytes_())
ppv = w.PTR()
print("QueryInterface hr", dt._vtbl.QueryInterface(this, ctypes.addressof(iid), ctypes.byref(ppv)), ppv.value == this)
dt._accept = True
print("DragOver(accept) hr", dt._vtbl.DragOver(this, 0, pt, ctypes.byref(eff)), "effect", eff.value, events[-1])
print("Drop hr", dt._vtbl.Drop(this, None, 0, pt, ctypes.byref(eff)), "effect", eff.value, events[-1])
print("DragLeave hr", dt._vtbl.DragLeave(this), events[-1])

# IDataObject real con un archivo (SHCreateDataObject) -> paths_from_dataobject
try:
    from dropwheel.droptarget import paths_from_dataobject
    target = os.path.abspath(__file__)
    shell32 = ctypes.WinDLL("shell32"); ole = ctypes.WinDLL("ole32")
    pidl = w.PTR()
    shell32.SHParseDisplayName.argtypes = [wt.LPCWSTR, w.PTR, ctypes.POINTER(w.PTR), wt.DWORD, ctypes.POINTER(wt.DWORD)]
    attrs = wt.DWORD(0)
    hr = shell32.SHParseDisplayName(target, None, ctypes.byref(pidl), 0, ctypes.byref(attrs))
    print("SHParseDisplayName", hr & 0xFFFFFFFF)
    child = w.PTR(); parent = w.PTR()
    shell32.SHBindToParent.argtypes = [w.PTR, ctypes.c_void_p, ctypes.POINTER(w.PTR), ctypes.POINTER(w.PTR)]
    iid_sf = (ctypes.c_ubyte * 16)(*w.GUID.from_string("000214E6-0000-0000-C000-000000000046").bytes_())
    hr = shell32.SHBindToParent(pidl, ctypes.addressof(iid_sf), ctypes.byref(parent), ctypes.byref(child))
    iid_do = (ctypes.c_ubyte * 16)(*w.GUID.from_string("0000010e-0000-0000-C000-000000000046").bytes_())
    dobj = w.PTR(); arr = (w.PTR * 1)(child.value)
    shell32.SHCreateDataObject.argtypes = [w.PTR, wt.UINT, ctypes.POINTER(w.PTR), w.PTR, ctypes.c_void_p, ctypes.POINTER(w.PTR)]
    hr = shell32.SHCreateDataObject(None, 1, arr, None, ctypes.addressof(iid_do), ctypes.byref(dobj))
    print("SHCreateDataObject", hr & 0xFFFFFFFF)
    if dobj.value:
        print("paths_from_dataobject ->", paths_from_dataobject(dobj.value))
except Exception as e:
    print("IDataObject test skipped:", repr(e))

# bombear mensajes un momento (y dejar que el capturador de pantalla saque la foto)
msg = w.MSG()
t0 = time.time()
while time.time() - t0 < float(os.environ.get("HOLD", "4")):
    while user32_peek(ctypes.byref(msg), None, 0, 0, 1) if False else False:
        pass
    time.sleep(0.1)
dt.revoke(); win.destroy()
print("SMOKE OK")
