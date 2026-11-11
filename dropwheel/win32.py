"""Definiciones mínimas de la API de Windows vía ctypes (solo se importa en Windows).

Todas las funciones llevan argtypes/restype explícitos: en Python de 64 bits, un puntero
sin tipo se trunca a 32 bits y la app se cae de forma intermitente.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes as wt

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
ole32 = ctypes.WinDLL("ole32", use_last_error=True)

HRESULT = ctypes.c_long
LRESULT = ctypes.c_ssize_t
WPARAM = ctypes.c_size_t
LPARAM = ctypes.c_ssize_t
PTR = ctypes.c_void_p

# --- constantes
WS_POPUP = 0x80000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
SW_HIDE = 0
SW_SHOWNOACTIVATE = 4
HWND_TOPMOST = -1
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOACTIVATE = 0x0010
SWP_SHOWWINDOW = 0x0040
ULW_ALPHA = 0x00000002
AC_SRC_OVER = 0
AC_SRC_ALPHA = 1
WM_DESTROY = 0x0002
WM_TIMER = 0x0113
WM_APP = 0x8000
VK_LBUTTON = 0x01
VK_SHIFT = 0x10
VK_CONTROL = 0x11
VK_MENU = 0x12
VK_TAB = 0x09
VK_SPACE = 0x20
VK_ESCAPE = 0x1B
CF_HDROP = 15
DVASPECT_CONTENT = 1
TYMED_HGLOBAL = 1
DROPEFFECT_NONE = 0
DROPEFFECT_COPY = 1
S_OK = 0
E_NOINTERFACE = ctypes.c_long(0x80004002).value
ERROR_ALREADY_EXISTS = 183
MONITOR_DEFAULTTONEAREST = 2
BI_RGB = 0
DIB_RGB_COLORS = 0


# --- estructuras
class POINT(ctypes.Structure):
    _fields_ = [("x", wt.LONG), ("y", wt.LONG)]


class SIZE(ctypes.Structure):
    _fields_ = [("cx", wt.LONG), ("cy", wt.LONG)]


class RECT(ctypes.Structure):
    _fields_ = [("left", wt.LONG), ("top", wt.LONG), ("right", wt.LONG), ("bottom", wt.LONG)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", wt.DWORD), ("rcMonitor", RECT), ("rcWork", RECT), ("dwFlags", wt.DWORD)]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte),
                ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG),
                ("biClrUsed", wt.DWORD), ("biClrImportant", wt.DWORD)]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE), ("hIcon", wt.HICON),
                ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH), ("lpszMenuName", wt.LPCWSTR),
                ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON)]


class MSG(ctypes.Structure):
    _fields_ = [("hwnd", wt.HWND), ("message", wt.UINT), ("wParam", WPARAM), ("lParam", LPARAM),
                ("time", wt.DWORD), ("pt", POINT)]


class FORMATETC(ctypes.Structure):
    _fields_ = [("cfFormat", wt.WORD), ("ptd", PTR), ("dwAspect", wt.DWORD), ("lindex", wt.LONG),
                ("tymed", wt.DWORD)]


class STGMEDIUM(ctypes.Structure):
    _fields_ = [("tymed", wt.DWORD), ("hGlobal", PTR), ("pUnkForRelease", PTR)]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]

    @classmethod
    def from_string(cls, s: str) -> "GUID":
        import uuid

        u = uuid.UUID(s)
        g = cls()
        g.Data1, g.Data2, g.Data3 = u.time_low, u.time_mid, u.time_hi_version
        for i, b in enumerate(u.bytes[8:]):
            g.Data4[i] = b
        return g

    def bytes_(self) -> bytes:
        return bytes(bytearray(ctypes.string_at(ctypes.addressof(self), ctypes.sizeof(self))))


# --- prototipos
def _proto(fn, restype, *argtypes):
    fn.restype = restype
    fn.argtypes = list(argtypes)
    return fn


GetModuleHandleW = _proto(kernel32.GetModuleHandleW, wt.HMODULE, wt.LPCWSTR)
CreateMutexW = _proto(kernel32.CreateMutexW, wt.HANDLE, PTR, wt.BOOL, wt.LPCWSTR)
GetCurrentProcess = _proto(kernel32.GetCurrentProcess, wt.HANDLE)
SetProcessWorkingSetSize = _proto(kernel32.SetProcessWorkingSetSize, wt.BOOL, wt.HANDLE, ctypes.c_size_t, ctypes.c_size_t)

RegisterClassExW = _proto(user32.RegisterClassExW, wt.ATOM, ctypes.POINTER(WNDCLASSEXW))
CreateWindowExW = _proto(user32.CreateWindowExW, wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD,
                         ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU,
                         wt.HINSTANCE, PTR)
DefWindowProcW = _proto(user32.DefWindowProcW, LRESULT, wt.HWND, wt.UINT, WPARAM, LPARAM)
DestroyWindow = _proto(user32.DestroyWindow, wt.BOOL, wt.HWND)
ShowWindow = _proto(user32.ShowWindow, wt.BOOL, wt.HWND, ctypes.c_int)
SetWindowPos = _proto(user32.SetWindowPos, wt.BOOL, wt.HWND, wt.HWND, ctypes.c_int, ctypes.c_int,
                      ctypes.c_int, ctypes.c_int, wt.UINT)
GetMessageW = _proto(user32.GetMessageW, wt.BOOL, ctypes.POINTER(MSG), wt.HWND, wt.UINT, wt.UINT)
TranslateMessage = _proto(user32.TranslateMessage, wt.BOOL, ctypes.POINTER(MSG))
DispatchMessageW = _proto(user32.DispatchMessageW, LRESULT, ctypes.POINTER(MSG))
PostMessageW = _proto(user32.PostMessageW, wt.BOOL, wt.HWND, wt.UINT, WPARAM, LPARAM)
PostQuitMessage = _proto(user32.PostQuitMessage, None, ctypes.c_int)
SetTimer = _proto(user32.SetTimer, ctypes.c_size_t, wt.HWND, ctypes.c_size_t, wt.UINT, PTR)
KillTimer = _proto(user32.KillTimer, wt.BOOL, wt.HWND, ctypes.c_size_t)
GetAsyncKeyState = _proto(user32.GetAsyncKeyState, ctypes.c_short, ctypes.c_int)
GetCursorPos = _proto(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(POINT))
WindowFromPoint = _proto(user32.WindowFromPoint, wt.HWND, POINT)
GetAncestor = _proto(user32.GetAncestor, wt.HWND, wt.HWND, wt.UINT)
GetClassNameW = _proto(user32.GetClassNameW, ctypes.c_int, wt.HWND, wt.LPWSTR, ctypes.c_int)
FindWindowW = _proto(user32.FindWindowW, wt.HWND, wt.LPCWSTR, wt.LPCWSTR)
GetDC = _proto(user32.GetDC, wt.HDC, wt.HWND)
ReleaseDC = _proto(user32.ReleaseDC, ctypes.c_int, wt.HWND, wt.HDC)
UpdateLayeredWindow = _proto(user32.UpdateLayeredWindow, wt.BOOL, wt.HWND, wt.HDC, ctypes.POINTER(POINT),
                             ctypes.POINTER(SIZE), wt.HDC, ctypes.POINTER(POINT), wt.COLORREF,
                             ctypes.POINTER(BLENDFUNCTION), wt.DWORD)
MonitorFromPoint = _proto(user32.MonitorFromPoint, wt.HMONITOR, POINT, wt.DWORD)
GetMonitorInfoW = _proto(user32.GetMonitorInfoW, wt.BOOL, wt.HMONITOR, ctypes.POINTER(MONITORINFO))

CreateCompatibleDC = _proto(gdi32.CreateCompatibleDC, wt.HDC, wt.HDC)
CreateDIBSection = _proto(gdi32.CreateDIBSection, wt.HBITMAP, wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
                          ctypes.POINTER(PTR), wt.HANDLE, wt.DWORD)
SelectObject = _proto(gdi32.SelectObject, wt.HGDIOBJ, wt.HDC, wt.HGDIOBJ)
DeleteObject = _proto(gdi32.DeleteObject, wt.BOOL, wt.HGDIOBJ)
DeleteDC = _proto(gdi32.DeleteDC, wt.BOOL, wt.HDC)
BitBlt = _proto(gdi32.BitBlt, wt.BOOL, wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD)
SRCCOPY = 0x00CC0020

DragQueryFileW = _proto(shell32.DragQueryFileW, wt.UINT, PTR, wt.UINT, wt.LPWSTR, wt.UINT)

OleInitialize = _proto(ole32.OleInitialize, HRESULT, PTR)
OleUninitialize = _proto(ole32.OleUninitialize, None)
RegisterDragDrop = _proto(ole32.RegisterDragDrop, HRESULT, wt.HWND, PTR)
RevokeDragDrop = _proto(ole32.RevokeDragDrop, HRESULT, wt.HWND)
ReleaseStgMedium = _proto(ole32.ReleaseStgMedium, None, ctypes.POINTER(STGMEDIUM))


def set_dpi_aware() -> None:
    """Coordenadas en píxeles físicos (necesario para que el cursor y la ventana coincidan)."""
    try:
        user32.SetProcessDpiAwarenessContext.argtypes = [PTR]
        user32.SetProcessDpiAwarenessContext(PTR(-4))  # PER_MONITOR_AWARE_V2
        return
    except (AttributeError, OSError):
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:  # noqa: BLE001
        try:
            user32.SetProcessDPIAware()
        except Exception:  # noqa: BLE001
            pass


def system_dpi_scale() -> float:
    try:
        user32.GetDpiForSystem.restype = wt.UINT
        return user32.GetDpiForSystem() / 96.0
    except Exception:  # noqa: BLE001
        return 1.0


def trim_memory() -> None:
    """Devuelve a Windows las páginas de RAM que no se están usando (baja el uso mostrado)."""
    try:
        SetProcessWorkingSetSize(GetCurrentProcess(), ctypes.c_size_t(-1).value, ctypes.c_size_t(-1).value)
    except Exception:  # noqa: BLE001
        pass
