"""IDropTarget escrito a mano con ctypes (sin comtypes ni pywin32).

Windows le avisa a esta clase cuando un archivo arrastrado (con el Explorador, el
Escritorio, etc.) entra, se mueve o se suelta sobre la ventana de la rueda.
"""
from __future__ import annotations

import ctypes
import struct
from ctypes import wintypes as wt

from . import win32 as w

IID_IUnknown = w.GUID.from_string("00000000-0000-0000-C000-000000000046").bytes_()
IID_IDropTarget = w.GUID.from_string("00000122-0000-0000-C000-000000000046").bytes_()

_X64 = struct.calcsize("P") == 8
DWORD = wt.DWORD
PDWORD = ctypes.POINTER(DWORD)

# POINTL se pasa POR VALOR: en x64 viaja en un solo registro de 64 bits; en x86 son dos DWORD.
if _X64:
    _EnterSig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, w.PTR, DWORD, ctypes.c_int64, PDWORD)
    _OverSig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, DWORD, ctypes.c_int64, PDWORD)
    _DropSig = _EnterSig
else:  # pragma: no cover
    _EnterSig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, w.PTR, DWORD, ctypes.c_long, ctypes.c_long, PDWORD)
    _OverSig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, DWORD, ctypes.c_long, ctypes.c_long, PDWORD)
    _DropSig = _EnterSig
_QISig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, w.PTR, ctypes.POINTER(w.PTR))
_RefSig = ctypes.WINFUNCTYPE(ctypes.c_ulong, w.PTR)
_LeaveSig = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR)


class _Vtbl(ctypes.Structure):
    _fields_ = [("QueryInterface", _QISig), ("AddRef", _RefSig), ("Release", _RefSig),
                ("DragEnter", _EnterSig), ("DragOver", _OverSig), ("DragLeave", _LeaveSig), ("Drop", _DropSig)]


class _Obj(ctypes.Structure):
    _fields_ = [("lpVtbl", ctypes.POINTER(_Vtbl))]


def _unpack_pt(*args) -> tuple[int, int]:
    if _X64:
        v = args[0] & 0xFFFFFFFFFFFFFFFF
        return ctypes.c_int32(v & 0xFFFFFFFF).value, ctypes.c_int32(v >> 32).value
    return args[0], args[1]


def paths_from_dataobject(pdata) -> list[str]:
    """Lista de rutas (CF_HDROP) que lleva el arrastre; vacía si no son archivos."""
    if not pdata:
        return []
    vt = ctypes.cast(ctypes.cast(pdata, ctypes.POINTER(w.PTR))[0], ctypes.POINTER(w.PTR))
    get_data = ctypes.WINFUNCTYPE(w.HRESULT, w.PTR, ctypes.POINTER(w.FORMATETC), ctypes.POINTER(w.STGMEDIUM))(vt[3])
    fmt = w.FORMATETC(w.CF_HDROP, None, w.DVASPECT_CONTENT, -1, w.TYMED_HGLOBAL)
    stg = w.STGMEDIUM()
    if get_data(pdata, ctypes.byref(fmt), ctypes.byref(stg)) != w.S_OK:
        return []
    paths: list[str] = []
    try:
        count = w.DragQueryFileW(stg.hGlobal, 0xFFFFFFFF, None, 0)
        for i in range(count):
            n = w.DragQueryFileW(stg.hGlobal, i, None, 0)
            buf = ctypes.create_unicode_buffer(n + 1)
            w.DragQueryFileW(stg.hGlobal, i, buf, n + 1)
            paths.append(buf.value)
    finally:
        w.ReleaseStgMedium(ctypes.byref(stg))
    return paths


class DropTarget:
    """Registra `hwnd` como destino de arrastre.

    Callbacks (todos en el hilo principal):
      on_enter(paths, x, y) -> bool      True si se aceptan estos archivos
      on_over(x, y) -> int               efecto DROPEFFECT_* a mostrar
      on_leave() -> None
      on_drop(x, y) -> int               efecto final (DROPEFFECT_COPY si se hizo algo)
    """

    def __init__(self, hwnd, on_enter, on_over, on_leave, on_drop):
        self.hwnd = hwnd
        self.on_enter, self.on_over, self.on_leave, self.on_drop = on_enter, on_over, on_leave, on_drop
        self._accept = False
        self._refs = 1

        def query_interface(this, riid, ppv):
            g = ctypes.string_at(riid, 16)
            if g in (IID_IUnknown, IID_IDropTarget):
                ppv[0] = this
                return w.S_OK
            ppv[0] = None
            return w.E_NOINTERFACE

        def add_ref(this):
            self._refs += 1
            return self._refs

        def release(this):
            self._refs -= 1
            return self._refs

        def drag_enter(this, pdata, keys, *rest):
            *pt, peffect = rest
            x, y = _unpack_pt(*pt)
            try:
                paths = paths_from_dataobject(pdata)
                self._accept = bool(paths) and bool(self.on_enter(paths, x, y))
            except Exception:  # noqa: BLE001
                self._accept = False
            peffect[0] = w.DROPEFFECT_COPY if self._accept else w.DROPEFFECT_NONE
            return w.S_OK

        def drag_over(this, keys, *rest):
            *pt, peffect = rest
            x, y = _unpack_pt(*pt)
            eff = w.DROPEFFECT_NONE
            if self._accept:
                try:
                    eff = self.on_over(x, y)
                except Exception:  # noqa: BLE001
                    eff = w.DROPEFFECT_NONE
            peffect[0] = eff
            return w.S_OK

        def drag_leave(this):
            try:
                self.on_leave()
            except Exception:  # noqa: BLE001
                pass
            self._accept = False
            return w.S_OK

        def drop(this, pdata, keys, *rest):
            *pt, peffect = rest
            x, y = _unpack_pt(*pt)
            eff = w.DROPEFFECT_NONE
            if self._accept:
                try:
                    eff = self.on_drop(x, y)
                except Exception:  # noqa: BLE001
                    eff = w.DROPEFFECT_NONE
            peffect[0] = eff  # COPY: el archivo original NO se mueve ni se borra
            self._accept = False
            return w.S_OK

        # Las referencias a los callbacks deben vivir tanto como el objeto COM
        self._cb = (_QISig(query_interface), _RefSig(add_ref), _RefSig(release), _EnterSig(drag_enter),
                    _OverSig(drag_over), _LeaveSig(drag_leave), _DropSig(drop))
        self._vtbl = _Vtbl(*self._cb)
        self._obj = _Obj(ctypes.pointer(self._vtbl))

    def register(self) -> None:
        hr = w.RegisterDragDrop(self.hwnd, ctypes.addressof(self._obj))
        if hr != w.S_OK:
            raise OSError(f"RegisterDragDrop falló: 0x{hr & 0xFFFFFFFF:08X}")

    def revoke(self) -> None:
        w.RevokeDragDrop(self.hwnd)
