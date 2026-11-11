"""Prueba la lógica del proceso residente (estados, rueda, soltar) con la API de Windows simulada."""
import os, sys, tempfile, types, unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PIL import Image


def fake_win32():
    m = types.ModuleType("dropwheel.win32")
    import ctypes
    m.ctypes = ctypes
    for k, v in dict(VK_LBUTTON=1, VK_SHIFT=0x10, VK_CONTROL=0x11, VK_MENU=0x12, VK_TAB=9, VK_SPACE=0x20,
                     DROPEFFECT_NONE=0, DROPEFFECT_COPY=1, MONITOR_DEFAULTTONEAREST=2, ERROR_ALREADY_EXISTS=183).items():
        setattr(m, k, v)

    class POINT(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]
    m.POINT = POINT
    m.keys = {}
    m.cursor = (0, 0)
    m.GetAsyncKeyState = lambda vk: 0x8000 if m.keys.get(vk) else 0
    def get_cursor(ref):
        ref._obj.x, ref._obj.y = m.cursor
        return True
    m.GetCursorPos = get_cursor
    m.system_dpi_scale = lambda: 1.0
    m.trim_memory = lambda: None
    m.WindowFromPoint = lambda pt: 1234
    m.GetAncestor = lambda h, f: 99
    m.FindWindowW = lambda a, b: 777
    m.MonitorFromPoint = lambda pt, f: 0
    m.MONITORINFO = type("MI", (), {})
    return m


class FakeWin:
    hwnd = 5
    def __init__(self): self.updates = []; self.visible = False; self.alpha = 255
    def set_alpha(self, a): self.alpha = a
    def update(self, b, W, H, x, y): self.updates.append((W, H, x, y, len(b)))
    def show(self): self.visible = True
    def hide(self): self.visible = False


class AgentLogic(unittest.TestCase):
    def setUp(self):
        self.w = fake_win32()
        self.patch = mock.patch.dict(sys.modules, {"dropwheel.win32": self.w})
        self.patch.start()
        sys.modules.pop("dropwheel.agent", None)
        import dropwheel
        dropwheel.win32 = self.w
        import importlib
        agent = importlib.import_module("dropwheel.agent")  # recarga limpia con el win32 simulado de ESTE test
        self.agent = agent
        with mock.patch.object(agent.settings, "load", return_value=dict(agent.settings.DEFAULTS)):
            self.a = agent.Agent()
        self.a.win = FakeWin()
        self.a._capture_backdrop = lambda l, t, W, H: Image.new('RGB', (W, H), (12, 12, 14))
        self.a._is_candidate = lambda x, y: True
        self.td = tempfile.TemporaryDirectory()
        self.png = os.path.join(self.td.name, "foto.png")
        Image.new("RGB", (50, 50), (200, 50, 50)).save(self.png)

    def tearDown(self):
        self.patch.stop()
        sys.modules.pop("dropwheel.agent", None)
        import dropwheel
        for name in ("agent", "win32"):
            if hasattr(dropwheel, name):
                delattr(dropwheel, name)
        self.td.cleanup()

    def tick(self, left, shift, pos):
        self.w.keys = {1: left, 0x10: shift}
        self.w.cursor = pos
        self.a._tick()

    def test_flow_convert(self):
        a, A = self.a, self.agent
        self.tick(True, False, (500, 500))           # botón abajo: empieza seguimiento
        self.tick(True, False, (560, 500))           # sin Shift: nada
        self.assertEqual(a.state, A.IDLE)
        self.tick(True, True, (600, 520))            # Shift + movimiento: rueda "fantasma"
        self.assertEqual(a.state, A.PLACEHOLDER)
        self.assertTrue(a.win.visible)
        self.assertTrue(a._on_enter([self.png], 600, 520))
        self.assertEqual(a.state, A.ACTIVE)
        self.assertEqual(a.page_order, ["convert", "actions"])
        wheel = a.wheel
        labels = a._current_labels()
        self.assertIn("JPG", labels)
        # mover sobre el segmento JPG
        i = labels.index("JPG")
        ang = __import__("math").radians(wheel.angle_of(i))
        x = a.win_pos[0] + wheel.cx + 130 * __import__("math").cos(ang)
        y = a.win_pos[1] + wheel.cy + 130 * __import__("math").sin(ang)
        self.assertEqual(a._on_over(int(x), int(y)), 1)
        self.assertEqual(a.hover, i)
        calls = []
        a._dispatch = lambda page, choice, paths: calls.append((page, choice, paths))
        self.assertEqual(a._on_drop(int(x), int(y)), 1)
        self.assertEqual(calls, [("convert", "JPG", [self.png])])
        self.assertEqual(a.state, A.IDLE)
        self.assertFalse(a.win.visible)

    def test_palette_from_backdrop_and_fade(self):
        a = self.a
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        self.assertTrue(a.palette.dark)                  # fondo casi negro -> vidrio oscuro
        self.assertIsNotNone(a.backdrop)
        a._on_enter([self.png], 160, 100)
        self.assertEqual(a.win.alpha, 90)                # empieza casi transparente
        import time
        time.sleep(0.2)
        self.tick(True, True, (170, 100))                # un tick de sondeo completa el fundido
        self.assertEqual(a.win.alpha, 255)
        a._hide()
        self.assertIsNone(a.backdrop)

    def test_drop_outside_and_leave(self):
        a, A = self.a, self.agent
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        a._on_enter([self.png], 160, 100)
        self.assertEqual(a._on_over(a.win_pos[0] + 2, a.win_pos[1] + 2), 0)   # fuera de la rueda
        self.assertEqual(a._on_drop(a.win_pos[0] + 2, a.win_pos[1] + 2), 0)
        self.assertEqual(a.state, A.IDLE)
        self.tick(False, False, (0, 0))
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        a._on_enter([self.png], 160, 100)
        a._on_leave()
        self.assertEqual(a.state, A.IDLE)
        self.tick(True, True, (200, 100))            # descartada: no reaparece hasta soltar el botón
        self.assertEqual(a.state, A.IDLE)

    def test_page_switch_and_actions(self):
        a = self.a
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        a._on_enter([self.png], 160, 100)
        a._switch_page()
        self.assertEqual(a.page_order[a.page_index], "actions")
        self.assertIn("CROP", a._current_labels())
        calls = []
        a._dispatch = lambda *x: calls.append(x)
        i = a._current_labels().index("CROP")
        import math
        ang = math.radians(a.wheel.angle_of(i))
        x = a.win_pos[0] + a.wheel.cx + 130 * math.cos(ang); y = a.win_pos[1] + a.wheel.cy + 130 * math.sin(ang)
        a._on_over(int(x), int(y)); a._on_drop(int(x), int(y))
        self.assertEqual(calls[0][:2], ("actions", "CROP"))

    def test_unsupported_and_multi(self):
        a, A = self.a, self.agent
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        zip_ = os.path.join(self.td.name, "x.zip"); open(zip_, "w").close()
        self.assertFalse(a._on_enter([zip_], 160, 100))
        self.assertEqual(a.state, A.IDLE)
        self.tick(False, False, (0, 0))
        self.tick(True, False, (100, 100)); self.tick(True, True, (160, 100))
        png2 = os.path.join(self.td.name, "b.png"); Image.new("RGB", (9, 9)).save(png2)
        self.assertTrue(a._on_enter([self.png, png2], 160, 100))
        self.assertEqual(a.page_order, ["convert"])  # varias imágenes: solo conversión


if __name__ == "__main__":
    unittest.main()
