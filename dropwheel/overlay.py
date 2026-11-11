"""Ventana flotante con transparencia por píxel donde se dibuja la rueda (solo Windows)."""
from __future__ import annotations

import ctypes

from . import win32 as w

CLASS_NAME = "DropWheelOverlay"


class LayeredWindow:
    """Ventana sin bordes, siempre encima, que no roba el foco y acepta transparencia por píxel."""

    def __init__(self, wndproc):
        self._wndproc = w.WNDPROC(wndproc)  # mantener viva la referencia
        hinst = w.GetModuleHandleW(None)
        wc = w.WNDCLASSEXW()
        wc.cbSize = ctypes.sizeof(w.WNDCLASSEXW)
        wc.lpfnWndProc = self._wndproc
        wc.hInstance = hinst
        wc.lpszClassName = CLASS_NAME
        if not w.RegisterClassExW(ctypes.byref(wc)):
            raise OSError(f"RegisterClassExW falló ({ctypes.get_last_error()})")
        ex = w.WS_EX_LAYERED | w.WS_EX_TOPMOST | w.WS_EX_TOOLWINDOW | w.WS_EX_NOACTIVATE
        self.hwnd = w.CreateWindowExW(ex, CLASS_NAME, "DropWheel", w.WS_POPUP, 0, 0, 1, 1, None, None, hinst, None)
        if not self.hwnd:
            raise OSError(f"CreateWindowExW falló ({ctypes.get_last_error()})")
        self.size = (0, 0)
        self._dc = None
        self._bmp = None
        self._old = None
        self._bits = None
        self.visible = False
        self.x = self.y = 0
        self.alpha = 255

    # --- superficie (DIB de 32 bits, arriba-abajo)
    def _ensure_surface(self, W: int, H: int) -> None:
        if self.size == (W, H) and self._bmp:
            return
        self._free_surface()
        screen = w.GetDC(None)
        self._dc = w.CreateCompatibleDC(screen)
        w.ReleaseDC(None, screen)
        bi = w.BITMAPINFO()
        bi.bmiHeader.biSize = ctypes.sizeof(w.BITMAPINFOHEADER)
        bi.bmiHeader.biWidth = W
        bi.bmiHeader.biHeight = -H
        bi.bmiHeader.biPlanes = 1
        bi.bmiHeader.biBitCount = 32
        bi.bmiHeader.biCompression = w.BI_RGB
        bits = w.PTR()
        self._bmp = w.CreateDIBSection(self._dc, ctypes.byref(bi), w.DIB_RGB_COLORS, ctypes.byref(bits), None, 0)
        if not self._bmp:
            raise OSError("CreateDIBSection falló")
        self._old = w.SelectObject(self._dc, self._bmp)
        self._bits = bits
        self.size = (W, H)

    def _free_surface(self) -> None:
        if self._dc:
            if self._old:
                w.SelectObject(self._dc, self._old)
            if self._bmp:
                w.DeleteObject(self._bmp)
            w.DeleteDC(self._dc)
        self._dc = self._bmp = self._old = self._bits = None
        self.size = (0, 0)

    def update(self, bgra: bytes, W: int, H: int, x: int, y: int) -> None:
        """Pinta `bgra` (BGRA premultiplicado, W*H*4 bytes) con su esquina en (x, y) de la pantalla."""
        self._ensure_surface(W, H)
        ctypes.memmove(self._bits, bgra, W * H * 4)
        pt_dst = w.POINT(x, y)
        sz = w.SIZE(W, H)
        pt_src = w.POINT(0, 0)
        blend = w.BLENDFUNCTION(w.AC_SRC_OVER, 0, self.alpha, w.AC_SRC_ALPHA)
        if not w.UpdateLayeredWindow(self.hwnd, None, ctypes.byref(pt_dst), ctypes.byref(sz), self._dc,
                                     ctypes.byref(pt_src), 0, ctypes.byref(blend), w.ULW_ALPHA):
            raise OSError(f"UpdateLayeredWindow falló ({ctypes.get_last_error()})")
        self.x, self.y = x, y

    def set_alpha(self, alpha: int) -> None:
        """Cambia la opacidad global (0-255) sin volver a copiar la imagen: sirve para el fundido de entrada."""
        if not self._bmp or alpha == self.alpha:
            return
        self.alpha = max(0, min(255, int(alpha)))
        pt_dst = w.POINT(self.x, self.y)
        sz = w.SIZE(*self.size)
        pt_src = w.POINT(0, 0)
        blend = w.BLENDFUNCTION(w.AC_SRC_OVER, 0, self.alpha, w.AC_SRC_ALPHA)
        w.UpdateLayeredWindow(self.hwnd, None, ctypes.byref(pt_dst), ctypes.byref(sz), self._dc,
                              ctypes.byref(pt_src), 0, ctypes.byref(blend), w.ULW_ALPHA)

    def show(self) -> None:
        if not self.visible:
            w.ShowWindow(self.hwnd, w.SW_SHOWNOACTIVATE)
            w.SetWindowPos(self.hwnd, w.HWND_TOPMOST, 0, 0, 0, 0, w.SWP_NOMOVE | w.SWP_NOSIZE | w.SWP_NOACTIVATE)
            self.visible = True

    def hide(self) -> None:
        if self.visible:
            w.ShowWindow(self.hwnd, w.SW_HIDE)
            self.visible = False
        self.alpha = 255
        self._free_surface()

    def destroy(self) -> None:
        self._free_surface()
        if self.hwnd:
            w.DestroyWindow(self.hwnd)
            self.hwnd = None
