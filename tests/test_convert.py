"""Pruebas del motor de conversión (corren en cualquier SO)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw  # noqa: E402

from dropwheel import catalog  # noqa: E402
from dropwheel.engine import convert  # noqa: E402


def make_image(path, size=(640, 480), alpha=False):
    img = Image.new("RGBA" if alpha else "RGB", size, (240, 240, 240, 255) if alpha else (240, 240, 240))
    d = ImageDraw.Draw(img)
    d.rectangle([40, 40, size[0] - 40, size[1] - 40], outline=(200, 40, 40), width=6)
    d.text((60, 60), "Hola DropWheel áéíóú ñ", fill=(0, 0, 0))
    img.save(path)


class ConvertTests(unittest.TestCase):
    def setUp(self):
        self.td = tempfile.TemporaryDirectory()
        self.d = self.td.name

    def tearDown(self):
        self.td.cleanup()

    def p(self, name):
        return os.path.join(self.d, name)

    def assertNewFile(self, outs, ext, original):
        self.assertTrue(outs, "no devolvió archivos")
        for o in outs:
            self.assertTrue(os.path.getsize(o) > 0, o)
            self.assertTrue(o.lower().endswith(ext), o)
            self.assertNotEqual(os.path.abspath(o), os.path.abspath(original))
        self.assertTrue(os.path.exists(original), "el original desapareció")

    def test_image_formats(self):
        src = self.p("foto.png")
        make_image(src, alpha=True)
        before = open(src, "rb").read()
        for fmt in ["JPG", "WEBP", "BMP", "TIFF", "HEIC", "AVIF", "PDF", "DOCX"]:
            outs = convert.convert(src, fmt)
            self.assertNewFile(outs, catalog.FORMAT_EXT[fmt], src)
        self.assertEqual(before, open(src, "rb").read(), "el original fue modificado")

    def test_roundtrip_heic_avif(self):
        src = self.p("a.png")
        make_image(src)
        for fmt in ["HEIC", "AVIF"]:
            out = convert.convert(src, fmt)[0]
            back = convert.convert(out, "PNG")[0]
            im = Image.open(back)
            self.assertEqual(im.size, (640, 480))

    def test_no_overwrite(self):
        src = self.p("x.png")
        make_image(src)
        a = convert.convert(src, "JPG")[0]
        b = convert.convert(src, "JPG")[0]
        self.assertNotEqual(a, b)
        self.assertTrue(b.endswith("x (1).jpg"))

    def test_pdf_chain(self):
        src = self.p("pagina.png")
        make_image(src)
        pdf = convert.convert(src, "PDF")[0]
        jpg = convert.convert(pdf, "JPG")
        self.assertNewFile(jpg, ".jpg", pdf)
        self.assertEqual(len(jpg), 1)
        png = convert.convert(pdf, "PNG")
        self.assertNewFile(png, ".png", pdf)
        docx = convert.convert(pdf, "DOCX")
        self.assertNewFile(docx, ".docx", pdf)

    def test_text_docs(self):
        t = self.p("nota.txt")
        with open(t, "w", encoding="utf-8") as f:
            f.write("Título\nHola mundo áéíóú\n\nSegundo párrafo con ñ.\n")
        pdf = convert.convert(t, "PDF")
        self.assertNewFile(pdf, ".pdf", t)
        docx = convert.convert(t, "DOCX")
        self.assertNewFile(docx, ".docx", t)
        txt = convert.convert(docx[0], "TXT")
        self.assertIn("Segundo párrafo con ñ.", open(txt[0], encoding="utf-8").read())
        pdf2 = convert.convert(docx[0], "PDF")
        self.assertNewFile(pdf2, ".pdf", docx[0])
        txt2 = convert.convert(pdf[0], "TXT")
        self.assertIn("Hola mundo", open(txt2[0], encoding="utf-8").read())

    def test_catalog(self):
        self.assertEqual(catalog.kind_of("a.JPG"), "image")
        self.assertNotIn("JPG", catalog.formats_for("a.jpeg"))
        self.assertIn("DOCX", catalog.formats_for("a.pdf"))
        self.assertEqual(catalog.formats_for("a.zip"), [])
        self.assertIn("convert", catalog.pages_for("a.png"))
        self.assertIn("actions", catalog.pages_for("a.png"))



class ActionTests(unittest.TestCase):
    def setUp(self):
        from dropwheel.engine import actions

        self.a = actions
        self.td = tempfile.TemporaryDirectory()
        self.src = os.path.join(self.td.name, "Page 001.jpg")
        make_image(self.src, size=(800, 600))

    def tearDown(self):
        self.td.cleanup()

    def size(self, p):
        with Image.open(p) as im:
            return im.size

    def test_crop(self):
        out = self.a.crop_image(self.src, (100, 100, 500, 400))
        self.assertTrue(out.endswith("Page 001 Cropped.jpg"))
        self.assertEqual(self.size(out), (400, 300))

    def test_edit(self):
        out = self.a.edit_image(self.src, rotate=90, grayscale=True, resize_pct=50)
        self.assertEqual(self.size(out), (300, 400))

    def test_add_bg(self):
        for name, spec in self.a.BG_PRESETS.items():
            out = self.a.add_background_file(self.src, spec, aspect=(1, 1))
            w, h = self.size(out)
            self.assertEqual(w, h, name)

    def test_compress(self):
        big = os.path.join(self.td.name, "big.jpg")
        Image.effect_noise((1600, 1200), 60).convert("RGB").save(big, quality=98)
        out = self.a.compress_image(big, quality=40)
        self.assertLess(os.path.getsize(out), os.path.getsize(big))
        png = os.path.join(self.td.name, "p.png")
        make_image(png, size=(800, 600))
        out2 = self.a.compress_image(png, quality=50)
        self.assertTrue(out2.endswith(".png"))
        est = self.a.estimate_compress(big, 40, None)
        self.assertGreater(est, 0)

    def test_annotate_redact(self):
        shapes = [
            {"type": "rect", "points": [(10, 10), (200, 100)], "color": "#ff0000", "width": 4},
            {"type": "arrow", "points": [(300, 300), (500, 400)], "color": "#00aa00", "width": 5},
            {"type": "pen", "points": [(0, 0), (50, 80), (120, 60)], "color": "#0000ff", "width": 6},
            {"type": "text", "points": [(60, 500)], "text": "Ñandú", "size": 40, "color": "#000000"},
            {"type": "highlight", "points": [(100, 100), (300, 200)], "color": "#ffff00"},
            {"type": "ellipse", "points": [(400, 100), (600, 250)], "color": "#aa00aa", "width": 3},
        ]
        out = self.a.annotate_image(self.src, shapes)
        self.assertTrue(out.endswith("Annotated.jpg"))
        red = self.a.redact_image(self.src, [(0, 0, 100, 100)])
        with Image.open(red) as im:
            self.assertLess(sum(im.convert("RGB").getpixel((50, 50))), 30)

    def test_metadata(self):
        exif = Image.Exif()
        exif[0x010F] = "CamaraTest"
        exif[0x0110] = "Modelo X"
        src = os.path.join(self.td.name, "e.jpg")
        Image.new("RGB", (64, 64), (10, 200, 10)).save(src, exif=exif)
        secs = dict(self.a.read_metadata(src))
        self.assertIn("EXIF", secs)
        self.assertTrue(any(v == "CamaraTest" for _, v in secs["EXIF"]))
        clean = self.a.strip_metadata(src)
        secs2 = dict(self.a.read_metadata(clean))
        self.assertFalse(any(v == "CamaraTest" for _, v in secs2.get("EXIF", [])))

    def test_pdf_compress_and_meta(self):
        pdf = convert.convert(self.src, "PDF")[0]
        out = self.a.compress_pdf(pdf)
        self.assertTrue(os.path.getsize(out) > 0)
        clean = self.a.strip_metadata(pdf)
        self.assertTrue(os.path.exists(clean))
        secs = dict(self.a.read_metadata(pdf))
        self.assertIn("PDF", secs)


if __name__ == "__main__":
    unittest.main()
