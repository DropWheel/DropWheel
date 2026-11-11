"""Acciones sobre archivos (recortar, comprimir, fondo, metadatos, etc.).

Todas crean una COPIA con un sufijo ("Cropped", "Compressed"...) y devuelven su ruta.
La parte gráfica (tkinter) vive en dropwheel/ui; aquí solo hay lógica pura y testeable.
"""
from __future__ import annotations

import io
import math
import os

from ..catalog import kind_of
from .convert import ConvertError, flatten, load_image, save_image
from .naming import output_path

_EXT_TO_FMT = {
    ".png": "PNG", ".jpg": "JPG", ".jpeg": "JPG", ".webp": "WEBP", ".bmp": "BMP",
    ".tif": "TIFF", ".tiff": "TIFF", ".heic": "HEIC", ".heif": "HEIC", ".avif": "AVIF", ".gif": "GIF",
}


def fmt_of(path: str) -> str:
    return _EXT_TO_FMT.get(os.path.splitext(path)[1].lower(), "PNG")


def save_like(src: str, img, suffix: str, quality: int = 95, force_fmt: str | None = None) -> str:
    """Guarda `img` junto a `src` con el mismo formato (o `force_fmt`) y un sufijo en el nombre."""
    from ..catalog import FORMAT_EXT as FEXT

    fmt = force_fmt or fmt_of(src)
    out = output_path(src, FEXT[fmt], suffix)
    save_image(img, out, fmt, quality=quality)
    return out


# ------------------------------------------------------------------- recorte
def crop_image(src: str, box: tuple[int, int, int, int], img=None) -> str:
    """box = (izq, arriba, der, abajo) en píxeles de la imagen original."""
    img = img if img is not None else load_image(src)
    l, t, r, b = [int(round(v)) for v in box]
    l, t = max(0, l), max(0, t)
    r, b = min(img.width, r), min(img.height, b)
    if r - l < 1 or b - t < 1:
        raise ConvertError("El área de recorte está vacía.")
    return save_like(src, img.crop((l, t, r, b)), " Cropped")


# ----------------------------------------------------------------- edición
def apply_edits(img, rotate: int = 0, flip_h: bool = False, flip_v: bool = False,
                brightness: float = 1.0, contrast: float = 1.0, saturation: float = 1.0,
                sharpness: float = 1.0, grayscale: bool = False, blur: float = 0.0,
                resize_pct: int = 100):
    from PIL import Image, ImageEnhance, ImageFilter, ImageOps

    out = img
    if rotate % 360:
        out = out.rotate(-rotate, expand=True)
    if flip_h:
        out = ImageOps.mirror(out)
    if flip_v:
        out = ImageOps.flip(out)
    has_alpha = "A" in out.mode
    alpha = out.getchannel("A") if has_alpha else None
    rgb = out.convert("RGB")
    if brightness != 1.0:
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
    if contrast != 1.0:
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
    if saturation != 1.0:
        rgb = ImageEnhance.Color(rgb).enhance(saturation)
    if sharpness != 1.0:
        rgb = ImageEnhance.Sharpness(rgb).enhance(sharpness)
    if blur > 0:
        rgb = rgb.filter(ImageFilter.GaussianBlur(blur))
    if grayscale:
        rgb = ImageOps.grayscale(rgb).convert("RGB")
    if alpha is not None:
        rgb = rgb.convert("RGBA")
        rgb.putalpha(alpha)
    if resize_pct != 100 and resize_pct > 0:
        w = max(1, int(rgb.width * resize_pct / 100))
        h = max(1, int(rgb.height * resize_pct / 100))
        rgb = rgb.resize((w, h), Image.LANCZOS)
    return rgb


def edit_image(src: str, **params) -> str:
    return save_like(src, apply_edits(load_image(src), **params), " Edited")


# -------------------------------------------------- anotaciones y tachado
def _hex(c):
    if isinstance(c, str) and c.startswith("#"):
        c = c.lstrip("#")
        return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(c)


def _font(size: int, bold: bool = True):
    from PIL import ImageFont

    names = (["segoeuib.ttf", "arialbd.ttf", "DejaVuSans-Bold.ttf"] if bold
             else ["segoeui.ttf", "arial.ttf", "DejaVuSans.ttf"])
    for n in names:
        try:
            return ImageFont.truetype(n, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size)
    except TypeError:
        return ImageFont.load_default()


def apply_annotations(img, shapes: list[dict]):
    """Dibuja formas sobre una copia de `img`. Coordenadas en píxeles de la imagen.

    shape = {type: 'pen'|'rect'|'ellipse'|'arrow'|'text'|'highlight'|'redact',
             color: '#rrggbb', width: int, points: [(x, y), ...], text: str, size: int}
    """
    from PIL import Image, ImageDraw

    base = img.convert("RGBA")
    for s in shapes:
        kind = s["type"]
        color = _hex(s.get("color", "#E5484D"))
        width = max(1, int(s.get("width", 4)))
        pts = [tuple(p) for p in s.get("points", [])]
        if not pts:
            continue
        if kind == "highlight":
            layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
            d = ImageDraw.Draw(layer)
            x0, y0 = pts[0]
            x1, y1 = pts[-1]
            d.rectangle([min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)], fill=color + (90,))
            base = Image.alpha_composite(base, layer)
            continue
        d = ImageDraw.Draw(base)
        if kind == "pen" and len(pts) > 1:
            d.line(pts, fill=color + (255,), width=width, joint="curve")
            r = width / 2
            for (x, y) in (pts[0], pts[-1]):
                d.ellipse([x - r, y - r, x + r, y + r], fill=color + (255,))
        elif kind in ("rect", "ellipse", "redact") and len(pts) >= 2:
            x0, y0 = pts[0]
            x1, y1 = pts[-1]
            box = [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]
            if kind == "rect":
                d.rectangle(box, outline=color + (255,), width=width)
            elif kind == "ellipse":
                d.ellipse(box, outline=color + (255,), width=width)
            else:
                d.rectangle(box, fill=(0, 0, 0, 255))
        elif kind == "arrow" and len(pts) >= 2:
            (x0, y0), (x1, y1) = pts[0], pts[-1]
            d.line([(x0, y0), (x1, y1)], fill=color + (255,), width=width)
            ang = math.atan2(y1 - y0, x1 - x0)
            head = max(14, width * 4)
            for da in (math.radians(155), -math.radians(155)):
                d.line([(x1, y1), (x1 + head * math.cos(ang + da), y1 + head * math.sin(ang + da))],
                       fill=color + (255,), width=width)
        elif kind == "text" and s.get("text"):
            f = _font(int(s.get("size", 32)))
            x, y = pts[0]
            d.text((x, y), s["text"], font=f, fill=color + (255,), stroke_width=0)
    return base


def annotate_image(src: str, shapes: list[dict], suffix: str = " Annotated") -> str:
    img = apply_annotations(load_image(src), shapes)
    return save_like(src, img, suffix)


def redact_image(src: str, boxes: list[tuple[int, int, int, int]]) -> str:
    """Tapa zonas con negro SÓLIDO y guarda sin metadatos (no se puede deshacer)."""
    shapes = [{"type": "redact", "points": [(b[0], b[1]), (b[2], b[3])]} for b in boxes]
    img = apply_annotations(load_image(src), shapes)
    return save_like(src, img, " Redacted")


# ------------------------------------------------------------------ fondo
def _gradient(size, c1, c2, angle_deg: float):
    from PIL import Image

    w, h = size
    a = math.radians(angle_deg)
    dx, dy = math.cos(a), math.sin(a)
    # proyección de cada píxel sobre la dirección del degradado
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    proj = [x * dx + y * dy for x, y in corners]
    lo, hi = min(proj), max(proj)
    span = (hi - lo) or 1.0
    # construir con un degradado 1D y rotar usando una imagen de gran tamaño es lento; hacemos mapeo por filas pequeñas
    small_w, small_h = max(2, w // 4), max(2, h // 4)
    img = Image.new("RGB", (small_w, small_h))
    px = img.load()
    for y in range(small_h):
        for x in range(small_w):
            t = (((x * 4) * dx + (y * 4) * dy) - lo) / span
            t = min(1.0, max(0.0, t))
            px[x, y] = tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    return img.resize(size, Image.BICUBIC)


BG_PRESETS = {
    "Atardecer": ("gradient", "#FFB347", "#FF5E62", 45),
    "Durazno": ("gradient", "#FFE0C2", "#FFB28A", 90),
    "Océano": ("gradient", "#36D1DC", "#5B86E5", 45),
    "Lavanda": ("gradient", "#C3B1FF", "#8EC5FC", 60),
    "Menta": ("gradient", "#B8F2E6", "#7ED6A8", 60),
    "Noche": ("gradient", "#232526", "#414345", 90),
    "Blanco": ("solid", "#FFFFFF"),
    "Negro": ("solid", "#111111"),
    "Transparente": ("transparent",),
}


def add_background(img, spec, padding_pct: int = 12, radius_pct: int = 3, shadow: bool = True,
                   aspect: tuple[int, int] | None = None):
    """Coloca `img` sobre un fondo. spec: ('solid', '#hex') | ('gradient', c1, c2, angle) | ('transparent',)."""
    from PIL import Image, ImageChops, ImageDraw, ImageFilter

    src = img.convert("RGBA")
    w, h = src.size
    pad = int(max(w, h) * padding_pct / 100)
    cw, ch = w + 2 * pad, h + 2 * pad
    if aspect:
        ar = aspect[0] / aspect[1]
        if cw / ch < ar:
            cw = int(round(ch * ar))
        else:
            ch = int(round(cw / ar))
    kind = spec[0]
    if kind == "solid":
        canvas = Image.new("RGBA", (cw, ch), _hex(spec[1]) + (255,))
    elif kind == "gradient":
        canvas = _gradient((cw, ch), _hex(spec[1]), _hex(spec[2]), spec[3] if len(spec) > 3 else 45).convert("RGBA")
    else:
        canvas = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))

    r = int(min(w, h) * radius_pct / 100)
    if r > 0:
        mask = Image.new("L", (w, h), 0)
        ImageDraw.Draw(mask).rounded_rectangle([0, 0, w - 1, h - 1], radius=r, fill=255)
        src.putalpha(ImageChops.multiply(src.getchannel("A"), mask))
    x, y = (cw - w) // 2, (ch - h) // 2
    if shadow:
        sh = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        blob = Image.new("RGBA", (w, h), (0, 0, 0, 120))
        blob.putalpha(ImageChops.multiply(blob.getchannel("A"), src.getchannel("A")))
        sh.paste(blob, (x, y + int(max(w, h) * 0.015)))
        sh = sh.filter(ImageFilter.GaussianBlur(max(6, int(max(w, h) * 0.02))))
        canvas = Image.alpha_composite(canvas, sh)
    canvas.alpha_composite(src, (x, y))
    return canvas


def add_background_file(src: str, spec, **kw) -> str:
    out_img = add_background(load_image(src), spec, **kw)
    # con fondo (no transparente) un JPG sigue siendo JPG; si no, PNG para conservar alfa
    fmt = "PNG" if (spec[0] == "transparent" or fmt_of(src) not in ("JPG", "WEBP")) else fmt_of(src)
    return save_like(src, out_img, " Background", force_fmt=fmt)


# -------------------------------------------------------------- compresión
def compress_image(src: str, quality: int = 70, max_side: int | None = None) -> str:
    """Reduce el peso. Formatos con pérdida: baja calidad. PNG/BMP/TIFF: cuantiza colores o pasa a JPG si no hay alfa."""
    from PIL import Image

    img = load_image(src)
    if max_side and max(img.size) > max_side:
        k = max_side / max(img.size)
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    fmt = fmt_of(src)
    original_size = os.path.getsize(src)
    if fmt in ("JPG", "WEBP", "HEIC", "AVIF"):
        out = save_like(src, img, " Compressed", quality=quality)
    elif fmt == "PNG":
        out = output_path(src, ".png", " Compressed")
        q = img.convert("RGBA") if "A" in img.mode else img.convert("RGB")
        colors = max(16, min(256, int(quality / 100 * 256)))
        try:
            pal = q.quantize(colors=colors, method=Image.FASTOCTREE if "A" in img.mode else Image.MEDIANCUT)
            pal.save(out, "PNG", optimize=True)
        except Exception:  # noqa: BLE001
            q.save(out, "PNG", optimize=True)
    else:  # BMP, TIFF, GIF -> formatos poco eficientes
        out = save_like(src, img, " Compressed", quality=quality, force_fmt="JPG" if "A" not in img.mode else "PNG")
    if os.path.getsize(out) >= original_size and fmt in ("PNG",):
        # no mejoró: al menos dejar PNG optimizado
        img.save(out, "PNG", optimize=True)
    return out


def estimate_compress(src: str, quality: int, max_side: int | None, img=None) -> int:
    """Tamaño estimado en bytes con esos ajustes (para la vista previa del diálogo)."""
    from PIL import Image

    img = img if img is not None else load_image(src)
    if max_side and max(img.size) > max_side:
        k = max_side / max(img.size)
        img = img.resize((max(1, int(img.width * k)), max(1, int(img.height * k))), Image.LANCZOS)
    buf = io.BytesIO()
    fmt = fmt_of(src)
    if fmt in ("JPG", "WEBP"):
        flatten(img).save(buf, "JPEG" if fmt == "JPG" else "WEBP", quality=quality)
    elif fmt == "PNG":
        colors = max(16, min(256, int(quality / 100 * 256)))
        q = img.convert("RGBA") if "A" in img.mode else img.convert("RGB")
        q.quantize(colors=colors).save(buf, "PNG", optimize=True)
    else:
        flatten(img).save(buf, "JPEG", quality=quality)
    return buf.tell()


def compress_pdf(src: str, image_quality: int = 60) -> str:
    from pypdf import PdfReader, PdfWriter

    out = output_path(src, ".pdf", " Compressed")
    try:
        reader = PdfReader(src)
        writer = PdfWriter(clone_from=reader)
    except Exception as e:  # noqa: BLE001
        raise ConvertError(f"No pude abrir el PDF: {e}") from e
    for page in writer.pages:
        try:
            for im in page.images:
                try:
                    im.replace(im.image.convert("RGB"), quality=image_quality)
                except Exception:  # noqa: BLE001
                    continue
        except Exception:  # noqa: BLE001
            pass
        try:
            page.compress_content_streams()
        except Exception:  # noqa: BLE001
            pass
    try:
        writer.compress_identical_objects(remove_identicals=True, remove_orphans=True)
    except Exception:  # noqa: BLE001
        pass
    with open(out, "wb") as f:
        writer.write(f)
    return out


# --------------------------------------------------------------- metadatos
def read_metadata(path: str) -> list[tuple[str, list[tuple[str, str]]]]:
    """[(sección, [(clave, valor), ...]), ...] listo para mostrar."""
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    st = os.stat(path)
    import datetime as _dt

    def ts(t):
        return _dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d %H:%M:%S")

    general = [
        ("Nombre", os.path.basename(path)),
        ("Carpeta", os.path.dirname(os.path.abspath(path))),
        ("Tamaño", f"{st.st_size:,} bytes"),
        ("Creado", ts(st.st_ctime)),
        ("Modificado", ts(st.st_mtime)),
    ]
    sections.append(("Archivo", general))
    kind = kind_of(path)
    if kind == "image":
        from PIL import ExifTags, Image

        from .convert import _register_openers

        _register_openers()
        with Image.open(path) as im:
            info = [("Formato", str(im.format)), ("Dimensiones", f"{im.width} × {im.height} px"), ("Modo", im.mode)]
            dpi = im.info.get("dpi")
            if dpi:
                info.append(("DPI", f"{dpi[0]:.0f} × {dpi[1]:.0f}"))
            sections.append(("Imagen", info))
            try:
                exif = im.getexif()
            except Exception:  # noqa: BLE001
                exif = {}
            rows = []
            for tag, val in exif.items():
                name = ExifTags.TAGS.get(tag, f"Tag {tag}")
                if isinstance(val, bytes):
                    val = f"<{len(val)} bytes>"
                rows.append((name, str(val)[:200]))
            try:
                sub = exif.get_ifd(0x8769)
                for tag, val in sub.items():
                    name = ExifTags.TAGS.get(tag, f"Tag {tag}")
                    if isinstance(val, bytes):
                        val = f"<{len(val)} bytes>"
                    rows.append((name, str(val)[:200]))
                gps = exif.get_ifd(0x8825)
                grows = [(ExifTags.GPSTAGS.get(t, str(t)), str(v)[:120]) for t, v in gps.items()]
            except Exception:  # noqa: BLE001
                grows = []
            if rows:
                sections.append(("EXIF", rows))
            if grows:
                sections.append(("GPS (ubicación)", grows))
            if not rows and not grows:
                sections.append(("EXIF", [("(sin metadatos EXIF)", "")]))
    elif kind == "pdf":
        from pypdf import PdfReader

        try:
            rd = PdfReader(path)
            md = rd.metadata or {}
            rows = [("Páginas", str(len(rd.pages)))]
            for k, v in md.items():
                rows.append((str(k).lstrip("/"), str(v)[:200]))
            sections.append(("PDF", rows))
        except Exception as e:  # noqa: BLE001
            sections.append(("PDF", [("Error", str(e))]))
    return sections


def strip_metadata(src: str) -> str:
    """Copia sin metadatos (EXIF/GPS en imágenes; autor/título/etc. en PDF)."""
    kind = kind_of(src)
    if kind == "image":
        from PIL import Image

        img = load_image(src)  # exif_transpose ya aplicó la orientación
        clean = Image.frombytes(img.mode, img.size, img.tobytes())
        if img.mode == "P" and img.getpalette():
            clean.putpalette(img.getpalette())
        return save_like(src, clean, " Clean")
    if kind == "pdf":
        from pypdf import PdfReader, PdfWriter

        out = output_path(src, ".pdf", " Clean")
        w = PdfWriter(clone_from=PdfReader(src))
        w.metadata = None
        w.add_metadata({"/Producer": "", "/Creator": "", "/Author": "", "/Title": ""})
        with open(out, "wb") as f:
            w.write(f)
        return out
    raise ConvertError("Este tipo de archivo no tiene metadatos que limpiar.")
