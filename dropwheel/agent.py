"""Proceso residente de DropWheel (solo Windows).

Qué hace, en resumen:
  1. Cada 40 ms mira (sin hooks globales) si estás arrastrando algo con el botón izquierdo y Shift.
  2. Si el arrastre empezó sobre el Escritorio o el Explorador, abre una ventana transparente
     con la rueda alrededor del cursor, registrada como destino de arrastre (IDropTarget).
  3. Al soltar sobre un segmento lanza un proceso aparte (worker) que crea la COPIA convertida.
     El archivo original nunca se mueve ni se modifica.
Todo lo pesado (conversiones, ventanas de edición) corre en procesos que se cierran al terminar.
"""
from __future__ import annotations

import ctypes
import json
import logging
import math
import os
import subprocess
import sys
import threading
import time

from . import APP_NAME, catalog, colors, settings
from . import win32 as w

log = logging.getLogger("dropwheel")

FADE_S = 0.14
POLL_MS = 40
TIMER_ID = 1
HUB_DWELL_S = 0.45
UP_FAILSAFE_S = 1.5
DRAG_START_PX = 8

EXPLORER_ROOTS = {"CabinetWClass", "ExploreWClass", "Progman", "WorkerW"}
EXPLORER_CHILDREN = {"SysListView32", "DirectUIHWND", "SHELLDLL_DefView", "UIItemsView"}

IDLE, PLACEHOLDER, ACTIVE = 0, 1, 2
PAGE_TITLES = {"convert": "Convertir", "actions": "Acciones"}


def _setup_logging() -> None:
    try:
        path = os.path.join(settings.config_dir(), "log.txt")
        logging.basicConfig(filename=path, level=logging.INFO, filemode="a",
                            format="%(asctime)s %(levelname)s %(message)s")
        if os.path.exists(path) and os.path.getsize(path) > 256 * 1024:
            open(path, "w").close()
    except Exception:  # noqa: BLE001
        pass


def _class_of(hwnd) -> str:
    if not hwnd:
        return ""
    buf = ctypes.create_unicode_buffer(128)
    w.GetClassNameW(hwnd, buf, 128)
    return buf.value


def _pythonw() -> str:
    exe = sys.executable
    if exe.lower().endswith("python.exe"):
        cand = exe[:-10] + "pythonw.exe"
        if os.path.exists(cand):
            return cand
    return exe


APP_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Agent:
    def __init__(self):
        self.cfg = settings.load()
        self.state = IDLE
        self.tracking = False
        self.candidate = False
        self.dismissed = False
        self.start = (0, 0)
        self.up_since = None
        self.tray = None
        self.scale = max(0.5, min(1.4, float(self.cfg["size"]))) * w.system_dpi_scale()
        # estado de la rueda activa
        self.wheel = None
        self.paths: list[str] = []
        self.pages: dict[str, list[str]] = {}
        self.page_order: list[str] = []
        self.page_index = 0
        self.hover = None
        self.hub_since = None
        self.hub_armed = False
        self.key_prev = {w.VK_TAB: False, w.VK_SPACE: False}
        self.win_pos = (0, 0)
        self.size_text = ""
        self.palette = None
        self.backdrop = None
        self.fade_t0 = None

    # ------------------------------------------------------------------ arranque
    def run(self) -> int:
        _setup_logging()
        mutex = w.CreateMutexW(None, False, "Local\\DropWheelSingleton")
        if not mutex or ctypes.get_last_error() == w.ERROR_ALREADY_EXISTS:
            return 0  # ya hay una copia corriendo
        w.set_dpi_aware()
        self.scale = max(0.5, min(1.4, float(self.cfg["size"]))) * w.system_dpi_scale()
        w.OleInitialize(None)

        from .overlay import LayeredWindow
        from .droptarget import DropTarget

        self.win = LayeredWindow(self._wndproc)
        self.target = DropTarget(self.win.hwnd, self._on_enter, self._on_over, self._on_leave, self._on_drop)
        self.target.register()
        w.SetTimer(self.win.hwnd, TIMER_ID, POLL_MS, None)
        self._start_tray()
        log.info("DropWheel iniciado (escala %.2f)", self.scale)
        w.trim_memory()

        msg = w.MSG()
        while w.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            w.TranslateMessage(ctypes.byref(msg))
            w.DispatchMessageW(ctypes.byref(msg))
        self._shutdown()
        return 0

    def _wndproc(self, hwnd, msg, wparam, lparam):
        try:
            if msg == w.WM_TIMER and wparam == TIMER_ID:
                self._tick()
                return 0
            if msg == w.WM_DESTROY:
                w.PostQuitMessage(0)
                return 0
        except Exception:  # noqa: BLE001
            log.exception("error en wndproc")
        return w.DefWindowProcW(hwnd, msg, wparam, lparam)

    def _shutdown(self) -> None:
        try:
            if self.tray:
                self.tray.stop()
            self.target.revoke()
            self.win.destroy()
            w.OleUninitialize()
        except Exception:  # noqa: BLE001
            pass

    def quit(self) -> None:
        w.PostMessageW(self.win.hwnd, w.WM_DESTROY, 0, 0)

    # ------------------------------------------------------------------ sondeo
    def _trigger_down(self) -> bool:
        vk = {"shift": w.VK_SHIFT, "ctrl": w.VK_CONTROL, "alt": w.VK_MENU}.get(self.cfg["trigger"], w.VK_SHIFT)
        return bool(w.GetAsyncKeyState(vk) & 0x8000)

    def _is_candidate(self, x: int, y: int) -> bool:
        if self.cfg.get("any_window"):
            return True
        hwnd = w.WindowFromPoint(w.POINT(x, y))
        if not hwnd or hwnd == self.win.hwnd:
            return False
        root = w.GetAncestor(hwnd, 2)  # GA_ROOT
        extra = set(self.cfg.get("extra_window_classes", []))
        c_root, c_child = _class_of(root), _class_of(hwnd)
        return (c_root in EXPLORER_ROOTS or c_child in EXPLORER_CHILDREN
                or c_root in extra or c_child in extra)

    def _drag_image_present(self) -> bool:
        if not self.cfg.get("require_drag_image", True):
            return True
        return bool(w.FindWindowW("SysDragImage", None))

    def _tick(self) -> None:
        if not self.cfg.get("enabled", True):
            return
        left = bool(w.GetAsyncKeyState(w.VK_LBUTTON) & 0x8000)
        now = time.monotonic()
        if not left:
            self.tracking = False
            self.dismissed = False
            if self.state == PLACEHOLDER:
                self._hide()
            elif self.state == ACTIVE:
                if self.up_since is None:
                    self.up_since = now
                elif now - self.up_since > UP_FAILSAFE_S:  # el Drop nunca llegó: no dejar la rueda colgada
                    self._hide()
            return
        self.up_since = None
        pt = w.POINT()
        w.GetCursorPos(ctypes.byref(pt))
        if not self.tracking:
            self.tracking = True
            self.start = (pt.x, pt.y)
            self.candidate = self._is_candidate(pt.x, pt.y)
            return
        if self.state == IDLE:
            if (self.candidate and not self.dismissed and self._trigger_down()
                    and math.hypot(pt.x - self.start[0], pt.y - self.start[1]) > DRAG_START_PX
                    and self._drag_image_present()):
                self._show_placeholder(pt.x, pt.y)
        elif self.state == ACTIVE:
            self._poll_active(now)

    def _poll_active(self, now: float) -> None:
        if self.fade_t0 is not None:
            k = (now - self.fade_t0) / FADE_S
            if k >= 1.0:
                self.win.set_alpha(255)
                self.fade_t0 = None
            else:
                self.win.set_alpha(int(90 + 165 * k))
        for vk in (w.VK_TAB, w.VK_SPACE):
            down = bool(w.GetAsyncKeyState(vk) & 0x8000)
            if down and not self.key_prev[vk]:
                self._switch_page()
            self.key_prev[vk] = down
        if self.hover == "hub" and self.hub_armed and len(self.page_order) > 1:
            if self.hub_since is None:
                self.hub_since = now
            elif now - self.hub_since > HUB_DWELL_S:
                self.hub_armed = False
                self._switch_page()
        else:
            self.hub_since = None

    # ------------------------------------------------------------------ rueda
    def _monitor_clamp(self, x: int, y: int, W: int, H: int, cx: int, cy: int) -> tuple[int, int]:
        left, top = x - cx, y - cy
        mon = w.MonitorFromPoint(w.POINT(x, y), w.MONITOR_DEFAULTTONEAREST)
        if mon:
            mi = w.MONITORINFO()
            mi.cbSize = ctypes.sizeof(w.MONITORINFO)
            if w.GetMonitorInfoW(mon, ctypes.byref(mi)):
                r = mi.rcMonitor
                left = max(r.left, min(left, r.right - W))
                top = max(r.top, min(top, r.bottom - H))
        return left, top

    def _system_accent(self):
        """Color de énfasis de Windows (Configuración > Personalización > Colores)."""
        try:
            import winreg

            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM") as k:
                v = winreg.QueryValueEx(k, "AccentColor")[0] & 0xFFFFFFFF  # 0xAABBGGRR
            return (v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF)
        except OSError:
            return None

    def _capture_backdrop(self, left: int, top: int, W: int, H: int):
        try:
            from .screencap import capture_region

            return capture_region(left, top, W, H)
        except Exception:  # noqa: BLE001
            log.exception("no pude capturar el fondo")
            return None

    def _make_palette(self, backdrop):
        accent = self.cfg.get("accent", "auto")
        if accent == "system":
            accent = self._system_accent()
        elif accent == "auto":
            accent = None
        style = self.cfg.get("style", "auto")
        if backdrop is None:
            return colors.default_palette()
        return colors.from_image(backdrop, style, accent)

    def _show_placeholder(self, x: int, y: int) -> None:
        from .wheelgfx import Wheel, to_premultiplied_bgra

        geo = Wheel(["", ""], self.scale)
        left, top = self._monitor_clamp(x, y, geo.W, geo.H, int(geo.cx), int(geo.cy))
        self.win_pos = (left, top)
        # Lo que hay detrás de la rueda (se captura ANTES de mostrar nuestra ventana)
        self.backdrop = self._capture_backdrop(left, top, geo.W, geo.H) if self.cfg.get("glass", True) else None
        self.palette = self._make_palette(self.backdrop)
        geo = Wheel(["", ""], self.scale, palette=self.palette)
        self.wheel = geo
        self.win.alpha = 255
        self.win.update(to_premultiplied_bgra(geo.placeholder()), geo.W, geo.H, left, top)
        self.win.show()
        self.state = PLACEHOLDER

    def _build_pages(self, paths: list[str]) -> dict[str, list[str]]:
        if any(catalog.kind_of(p) is None for p in paths):
            return {}
        fmts = catalog.formats_for(paths[0])
        for p in paths[1:]:
            ok = set(catalog.formats_for(p))
            fmts = [f for f in fmts if f in ok]
        pages: dict[str, list[str]] = {}
        if fmts:
            pages["convert"] = fmts
        if len(paths) == 1:
            acts = catalog.actions_for(paths[0])
            if acts:
                pages["actions"] = acts
        return pages

    def _current_labels(self) -> list[str]:
        return self.pages[self.page_order[self.page_index]]

    def _make_wheel(self) -> None:
        from .wheelgfx import Wheel

        key = self.page_order[self.page_index]
        self.wheel = Wheel(self._current_labels(), self.scale, icons=(key == "actions"),
                           palette=self.palette, backdrop=self.backdrop)
        self.hover = "hub"
        self.hub_since = None
        self.hub_armed = False

    def _redraw(self) -> None:
        from .wheelgfx import to_premultiplied_bgra

        wheel = self.wheel
        titles = tuple(PAGE_TITLES[k] for k in self.page_order)
        img = wheel.render(hover=self.hover, center_text=self.size_text, page_labels=titles,
                           page_index=self.page_index, copy_badge=True)
        self.win.update(to_premultiplied_bgra(img), wheel.W, wheel.H, *self.win_pos)

    def _switch_page(self) -> None:
        if len(self.page_order) < 2:
            return
        self.page_index = (self.page_index + 1) % len(self.page_order)
        self._make_wheel()
        self._redraw()

    def _hide(self) -> None:
        self.win.hide()
        self.state = IDLE
        self.wheel = None
        self.paths, self.pages, self.page_order = [], {}, []
        self.hover = None
        self.up_since = None
        self.backdrop = None
        self.fade_t0 = None
        w.trim_memory()

    # ------------------------------------------------------------------ callbacks de arrastre
    def _on_enter(self, paths: list[str], x: int, y: int) -> bool:
        if self.state == IDLE:
            return False
        pages = self._build_pages(paths)
        if not pages:
            self._hide()
            self.dismissed = True
            return False
        self.paths, self.pages = paths, pages
        self.page_order = [k for k in ("convert", "actions") if k in pages]
        self.page_index = 0
        self.size_text = catalog.human_size(paths[0]) if len(paths) == 1 else f"{len(paths)} archivos"
        self._make_wheel()
        self.state = ACTIVE
        if self.cfg.get("animations", True):
            self.win.alpha = 90
            self.fade_t0 = time.monotonic()
        self._redraw()
        return True

    def _hit(self, x: int, y: int):
        if self.wheel is None:
            return None
        return self.wheel.hit_test(x - self.win_pos[0], y - self.win_pos[1])

    def _on_over(self, x: int, y: int) -> int:
        if self.state != ACTIVE:
            return w.DROPEFFECT_NONE
        hit = self._hit(x, y)
        if hit != self.hover:
            self.hover = hit
            if isinstance(hit, int):
                self.hub_armed = True
            self._redraw()
        return w.DROPEFFECT_COPY if isinstance(hit, int) else w.DROPEFFECT_NONE

    def _on_leave(self) -> None:
        if self.state == ACTIVE:
            self._hide()
            self.dismissed = True

    def _on_drop(self, x: int, y: int) -> int:
        hit = self._hit(x, y)
        if not isinstance(hit, int) or self.state != ACTIVE:
            self._hide()
            return w.DROPEFFECT_NONE
        page = self.page_order[self.page_index]
        choice = self._current_labels()[hit]
        paths = list(self.paths)
        self._hide()
        self._dispatch(page, choice, paths)
        return w.DROPEFFECT_COPY  # copia: el original queda intacto

    # ------------------------------------------------------------------ trabajo
    def _dispatch(self, page: str, choice: str, paths: list[str]) -> None:
        if page == "convert":
            args = ["convert", choice] + paths
        else:
            args = ["action", choice] + paths[:1]
        threading.Thread(target=self._run_worker, args=(args, page, choice), daemon=True).start()

    def _run_worker(self, args: list[str], page: str, choice: str) -> None:
        cmd = [_pythonw(), "-m", "dropwheel.worker"] + args
        env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONPATH=APP_ROOT)
        if self.palette is not None:
            env["DROPWHEEL_PALETTE"] = self.palette.to_json()  # las ventanas usan los mismos colores que la rueda
        try:
            p = subprocess.Popen(cmd, cwd=APP_ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                 creationflags=0x08000000)  # CREATE_NO_WINDOW
            out, err = p.communicate()
        except Exception as e:  # noqa: BLE001
            log.exception("no pude lanzar el worker")
            self._notify("No pude iniciar la conversión", str(e))
            return
        result = {}
        for line in reversed(out.decode("utf-8", "replace").splitlines()):
            line = line.strip()
            if line.startswith("{"):
                try:
                    result = json.loads(line)
                    break
                except ValueError:
                    continue
        if err:
            log.info("worker stderr: %s", err.decode("utf-8", "replace")[-2000:])
        if result.get("ok"):
            outs = result.get("outputs", [])
            if outs:
                names = ", ".join(os.path.basename(o) for o in outs[:3]) + (" …" if len(outs) > 3 else "")
                self._notify("Listo ✔", names)
                if self.cfg.get("reveal_in_explorer"):
                    subprocess.Popen(["explorer", "/select,", os.path.normpath(outs[0])])
        elif result.get("cancelled"):
            pass
        else:
            self._notify("No se pudo completar", result.get("error") or "Revisa log.txt en %APPDATA%\\DropWheel")

    def _notify(self, title: str, msg: str) -> None:
        if self.cfg.get("notify", True) and self.tray:
            try:
                self.tray.notify(msg, title)
            except Exception:  # noqa: BLE001
                pass

    # ------------------------------------------------------------------ bandeja
    def _tray_image(self):
        from .icon import make_icon

        return make_icon(64)

    def _start_tray(self) -> None:
        try:
            import pystray
        except ImportError:
            log.warning("pystray no está instalado: sin icono de bandeja")
            return

        def toggle_enabled(icon, item):
            self.cfg["enabled"] = not self.cfg.get("enabled", True)
            settings.save(self.cfg)

        def toggle_autostart(icon, item):
            set_autostart(not is_autostart())

        def set_size(v):
            def _f(icon, item):
                self.cfg["size"] = v
                settings.save(self.cfg)
                self.scale = v * w.system_dpi_scale()
            return _f

        def is_size(v):
            return lambda item: abs(float(self.cfg["size"]) - v) < 0.01

        def open_settings(icon, item):
            settings.save(self.cfg)
            os.startfile(os.path.join(settings.config_dir(), "settings.json"))  # type: ignore[attr-defined]

        def reload_settings(icon, item):
            self.cfg = settings.load()
            self.scale = float(self.cfg["size"]) * w.system_dpi_scale()

        def quit_(icon, item):
            self.quit()

        menu = pystray.Menu(
            pystray.MenuItem("DropWheel activo", toggle_enabled, checked=lambda i: self.cfg.get("enabled", True)),
            pystray.MenuItem("Iniciar con Windows", toggle_autostart, checked=lambda i: is_autostart()),
            pystray.MenuItem("Tamaño de la rueda", pystray.Menu(
                pystray.MenuItem("Compacta", set_size(0.7), checked=is_size(0.7), radio=True),
                pystray.MenuItem("Normal", set_size(0.85), checked=is_size(0.85), radio=True),
                pystray.MenuItem("Grande", set_size(1.0), checked=is_size(1.0), radio=True),
            )),
            pystray.MenuItem("Abrir configuración…", open_settings),
            pystray.MenuItem("Recargar configuración", reload_settings),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Salir", quit_),
        )
        try:
            self.tray = pystray.Icon(APP_NAME, self._tray_image(), "DropWheel · mantén Shift y arrastra un archivo", menu)
            self.tray.run_detached()
        except Exception:  # noqa: BLE001
            self.tray = None
            log.exception("no pude crear el icono de la bandeja")


# ---------------------------------------------------------------------- inicio con Windows
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_autostart() -> bool:
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as k:
            winreg.QueryValueEx(k, APP_NAME)
            return True
    except OSError:
        return False


def set_autostart(on: bool) -> None:
    import winreg

    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if on:
            launcher = os.path.join(APP_ROOT, "DropWheel.pyw")
            winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ, f'"{_pythonw()}" "{launcher}"')
        else:
            try:
                winreg.DeleteValue(k, APP_NAME)
            except OSError:
                pass


def main() -> int:
    if sys.platform != "win32":
        print("DropWheel solo funciona en Windows.")
        return 1
    try:
        return Agent().run()
    except Exception:  # noqa: BLE001
        _setup_logging()
        logging.getLogger("dropwheel").exception("fallo fatal")
        import traceback

        traceback.print_exc()  # visible si lo lanzas con depurar.bat
        return 1
