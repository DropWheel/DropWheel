"""Captura de una región de la pantalla (lo que hay detrás de la rueda) con GDI. Solo Windows."""
from __future__ import annotations

import ctypes

from PIL import Image

from . import win32 as w


def capture_region(x: int, y: int, W: int, H: int) -> Image.Image | None:
    """Imagen RGB de la región (coordenadas de pantalla). No incluye ventanas 'layered' (la miniatura de arrastre)."""
    screen = w.GetDC(None)
    if not screen:
        return None
    mem = w.CreateCompatibleDC(screen)
    bi = w.BITMAPINFO()
    bi.bmiHeader.biSize = ctypes.sizeof(w.BITMAPINFOHEADER)
    bi.bmiHeader.biWidth = W
    bi.bmiHeader.biHeight = -H  # de arriba hacia abajo
    bi.bmiHeader.biPlanes = 1
    bi.bmiHeader.biBitCount = 32
    bi.bmiHeader.biCompression = w.BI_RGB
    bits = w.PTR()
    bmp = w.CreateDIBSection(mem, ctypes.byref(bi), w.DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
    img = None
    try:
        if bmp and bits.value:
            old = w.SelectObject(mem, bmp)
            if w.BitBlt(mem, 0, 0, W, H, screen, x, y, w.SRCCOPY):
                raw = ctypes.string_at(bits.value, W * H * 4)
                img = Image.frombuffer("RGBA", (W, H), raw, "raw", "BGRA", 0, 1).convert("RGB")
            w.SelectObject(mem, old)
    finally:
        if bmp:
            w.DeleteObject(bmp)
        w.DeleteDC(mem)
        w.ReleaseDC(None, screen)
    return img
