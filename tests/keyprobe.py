import ctypes, sys, time
from ctypes import wintypes as wt
u = ctypes.WinDLL("user32")
u.GetAsyncKeyState.restype = ctypes.c_short
class P(ctypes.Structure): _fields_ = [("x", wt.LONG), ("y", wt.LONG)]
focus = len(sys.argv) > 1 and sys.argv[1] == "focus"
if focus:
    import tkinter as tk
    r = tk.Tk(); r.geometry("200x100+0+0"); r.update()
t0 = time.time(); last = None
while time.time() - t0 < 7:
    if focus: r.update()
    p = P(); u.GetCursorPos(ctypes.byref(p))
    st = (bool(u.GetAsyncKeyState(1) & 0x8000), bool(u.GetAsyncKeyState(0x10) & 0x8000), p.x, p.y)
    if st != last: print(round(time.time() - t0, 1), st, flush=True); last = st
    time.sleep(0.05)
