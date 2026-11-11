"""Paleta adaptativa y dibujo de la rueda con vidrio."""
import os, sys, unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from PIL import Image, ImageDraw

from dropwheel import colors
from dropwheel.wheelgfx import Wheel, to_premultiplied_bgra


def solid(c, size=(120, 120)):
    return Image.new("RGB", size, c)


class ColorTests(unittest.TestCase):
    def test_black_wallpaper_is_dark_glass_with_neutral_accent(self):
        p = colors.from_image(solid((8, 8, 10)))
        self.assertTrue(p.dark)
        self.assertTrue(p.neutral_accent)
        self.assertLess(colors.luminance(p.tint), 0.12)
        self.assertGreater(colors.luminance(p.tint), 0.02)   # no es negro puro: hay contraste con el fondo
        self.assertGreater(colors.luminance(p.text), 0.8)

    def test_light_wallpaper_is_light_glass(self):
        p = colors.from_image(solid((240, 238, 232)))
        self.assertFalse(p.dark)
        self.assertGreater(colors.luminance(p.tint), 0.7)
        self.assertLess(colors.luminance(p.text), 0.2)

    def test_colorful_wallpaper_gets_accent_and_tinted_glass(self):
        im = Image.new("RGB", (120, 120), (20, 60, 150))
        ImageDraw.Draw(im).rectangle([0, 0, 120, 50], fill=(240, 130, 40))
        p = colors.from_image(im)
        self.assertFalse(p.neutral_accent)
        r, g, b = p.accent
        self.assertTrue(r > b or b > r)  # tiene tono
        self.assertTrue(max(p.accent) - min(p.accent) > 80)  # saturado
        tr, tg, tb = p.tint
        self.assertTrue(max(p.tint) - min(p.tint) >= 6)  # el vidrio lleva algo del color del fondo

    def test_overrides(self):
        p = colors.from_image(solid((8, 8, 10)), style="light", accent="#ff0066")
        self.assertFalse(p.dark)
        self.assertEqual(p.accent, (255, 0, 102))
        q = colors.from_image(solid((240, 240, 240)), style="dark")
        self.assertTrue(q.dark)

    def test_json_roundtrip(self):
        p = colors.from_image(solid((30, 80, 200)))
        self.assertEqual(colors.Palette.from_json(p.to_json()), p)

    def test_wheel_renders_with_backdrop_and_is_hit_testable(self):
        bd = solid((10, 10, 12), (360, 394))
        p = colors.from_image(bd)
        w = Wheel(["PNG", "JPG", "PDF"], 0.85, False, p, bd)
        img = w.render(hover=1, center_text="1.2 MB", page_labels=("Convertir", "Acciones"), copy_badge=True)
        self.assertEqual(img.size, (w.W, w.H))
        self.assertEqual(len(to_premultiplied_bgra(img)), w.W * w.H * 4)
        # el hueco entre segmentos y el disco entero deben tener alfa > 0 para recibir el arrastre
        self.assertGreater(img.getpixel((int(w.cx), int(w.cy - w.r_out + 20)))[3], 200)
        self.assertGreater(img.getpixel((int(w.cx + 60), int(w.cy + 60)))[3], 0)
        # fuera de la rueda (esquina) no hay nada
        self.assertEqual(img.getpixel((2, 2))[3], 0)
        ph = w.placeholder()
        self.assertEqual(ph.getpixel((int(w.cx + w.r_out - 10), int(w.cy)))[3], 2)

    def test_wheel_without_backdrop_and_light(self):
        p = colors.from_image(solid((240, 240, 240)))
        w = Wheel(["COMPRESS", "METADATA", "EDIT", "ANNOTATE", "ADD BG", "CROP", "REDACT"], 1.0, True, p, None)
        self.assertEqual(w.render(hover=None).size, (w.W, w.H))
        for i in range(w.n):
            w.render(hover=i)


if __name__ == "__main__":
    unittest.main()
