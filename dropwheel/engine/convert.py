"""Motor de conversión. Cada función devuelve la lista de archivos NUEVOS creados.

Se importa solo en procesos "worker" (no en el residente) para no gastar RAM.
Nunca modifica el archivo original.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile

from ..catalog import FORMAT_EXT, kind_of
from .naming import output_path, unique_path


class ConvertError(Exception):
    pass


# ----------------------------------------------------------------- imágenes
_openers_ready = False


def _register_openers() -> None:
    global _openers_ready
    if _openers_ready:
        return
    try:
        import pillow_heif  # type: ignore

        pillow_heif.register_heif_opener()
        try:
            pillow_heif.register_avif_opener()
        except Exception:
            pass
    except ImportError:
        pass
    _openers_ready = True


def load_image(path: str):
    """Abre una imagen (incluye HEIC/AVIF), aplica orientación EXIF y toma el 1er cuadro."""
    from PIL import Image, ImageOps

    _register_openers()
    try:
        img = Image.open(path)
        img.load()
    except Exception as e:  # noqa: BLE001
        raise ConvertError(f"No pude abrir la imagen: {e}") from e
    if getattr(img, "n_frames", 1) > 1:
        img.seek(0)
    img = ImageOps.exif_transpose(img)
    return img


def flatten(img, bg=(255, 255, 255)):
    """Quita la transparencia sobre un fondo sólido y devuelve RGB."""
    from PIL import Image

    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, bg)
        base.paste(rgba, mask=rgba.split()[3])
        return base
    return img.convert("RGB")


def save_image(img, out: str, fmt: str, quality: int = 92) -> None:
    """Guarda `img` en `out` con el formato `fmt` ('PNG', 'JPG', ...)."""
    _register_openers()
    fmt = fmt.upper()
    try:
        if fmt == "JPG":
            flatten(img).save(out, "JPEG", quality=quality, optimize=True, subsampling=0 if quality >= 90 else 2)
        elif fmt == "PNG":
            img.save(out, "PNG", optimize=True)
        elif fmt == "WEBP":
            img.save(out, "WEBP", quality=quality, method=4)
        elif fmt == "BMP":
            flatten(img).save(out, "BMP")
        elif fmt == "TIFF":
            img.save(out, "TIFF", compression="tiff_lzw")
        elif fmt == "GIF":
            img.convert("RGBA" if "A" in img.mode else "RGB").save(out, "GIF")
        elif fmt == "HEIC":
            img.convert("RGBA" if "A" in img.mode else "RGB").save(out, "HEIF", quality=quality)
        elif fmt == "AVIF":
            img.convert("RGBA" if "A" in img.mode else "RGB").save(out, "AVIF", quality=quality)
        else:
            raise ConvertError(f"Formato de imagen no soportado: {fmt}")
    except ConvertError:
        raise
    except Exception as e:  # noqa: BLE001
        if os.path.exists(out):
            try:
                os.remove(out)
            except OSError:
                pass
        raise ConvertError(f"No pude guardar como {fmt}: {e}") from e


def image_to_image(src: str, fmt: str) -> list[str]:
    img = load_image(src)
    out = output_path(src, FORMAT_EXT[fmt])
    save_image(img, out, fmt)
    return [out]


def image_to_pdf(src: str) -> list[str]:
    img = flatten(load_image(src))
    out = output_path(src, ".pdf")
    try:
        img.save(out, "PDF", resolution=150.0)
    except Exception as e:  # noqa: BLE001
        raise ConvertError(f"No pude crear el PDF: {e}") from e
    return [out]


def image_to_docx(src: str) -> list[str]:
    from docx import Document
    from docx.shared import Inches

    img = flatten(load_image(src))
    out = output_path(src, ".docx")
    with tempfile.TemporaryDirectory() as td:
        tmp = os.path.join(td, "img.png")
        img.save(tmp, "PNG")
        doc = Document()
        sec = doc.sections[0]
        max_w = (sec.page_width - sec.left_margin - sec.right_margin) / 914400  # EMU -> pulgadas
        w, h = img.size
        width_in = min(max_w, w / 150.0) if w else max_w
        doc.add_picture(tmp, width=Inches(width_in))
        doc.save(out)
    return [out]


# ---------------------------------------------------------------------- PDF
def _pdf_open(path: str):
    import pypdfium2 as pdfium

    try:
        return pdfium.PdfDocument(path)
    except Exception as e:  # noqa: BLE001
        raise ConvertError(f"No pude abrir el PDF (¿protegido con contraseña?): {e}") from e


def pdf_to_images(src: str, fmt: str, dpi: int = 200) -> list[str]:
    pdf = _pdf_open(src)
    try:
        n = len(pdf)
        outs: list[str] = []
        folder, name = os.path.split(os.path.abspath(src))
        stem = os.path.splitext(name)[0]
        for i in range(n):
            page = pdf[i]
            bitmap = page.render(scale=dpi / 72.0)
            img = bitmap.to_pil()
            suffix = "" if n == 1 else f" - página {i + 1}"
            out = unique_path(folder, stem + suffix, FORMAT_EXT[fmt])
            save_image(img, out, fmt)
            outs.append(out)
        return outs
    finally:
        pdf.close()


def pdf_to_txt(src: str) -> list[str]:
    pdf = _pdf_open(src)
    try:
        parts = []
        for i in range(len(pdf)):
            tp = pdf[i].get_textpage()
            parts.append(tp.get_text_range())
        text = "\n\n".join(p.replace("\r\n", "\n") for p in parts).strip()
    finally:
        pdf.close()
    out = output_path(src, ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(text + "\n")
    return [out]


def pdf_to_docx(src: str) -> list[str]:
    out = output_path(src, ".docx")
    try:
        from pdf2docx import Converter  # type: ignore

        cv = Converter(src)
        try:
            cv.convert(out)
        finally:
            cv.close()
        return [out]
    except ImportError:
        pass
    except Exception:  # noqa: BLE001
        if os.path.exists(out):
            try:
                os.remove(out)
            except OSError:
                pass
    # Respaldo: solo el texto
    from docx import Document

    pdf = _pdf_open(src)
    try:
        doc = Document()
        for i in range(len(pdf)):
            text = pdf[i].get_textpage().get_text_range().replace("\r\n", "\n")
            for para in text.split("\n"):
                doc.add_paragraph(para)
            if i < len(pdf) - 1:
                doc.add_page_break()
        doc.save(out)
    finally:
        pdf.close()
    return [out]


# --------------------------------------------------------------------- DOCX
def _docx_lines(src: str) -> list[tuple[str, str]]:
    """[(estilo, texto)] con párrafos y filas de tablas, en orden del documento."""
    from docx import Document
    from docx.table import Table
    from docx.text.paragraph import Paragraph

    try:
        doc = Document(src)
    except Exception as e:  # noqa: BLE001
        raise ConvertError(f"No pude abrir el DOCX: {e}") from e
    lines: list[tuple[str, str]] = []
    for child in doc.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            p = Paragraph(child, doc)
            lines.append((p.style.name if p.style is not None else "", p.text))
        elif tag == "tbl":
            t = Table(child, doc)
            for row in t.rows:
                lines.append(("Table", "  |  ".join(c.text.strip() for c in row.cells)))
    return lines


def docx_to_txt(src: str) -> list[str]:
    out = output_path(src, ".txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(t for _, t in _docx_lines(src)) + "\n")
    return [out]


def _try_word(src: str, out: str) -> bool:
    """Microsoft Word por COM (solo Windows, solo si está instalado)."""
    if sys.platform != "win32":
        return False
    ps = (
        "$w=New-Object -ComObject Word.Application;$w.Visible=$false;"
        "try{$d=$w.Documents.Open($args[0],$false,$true);$d.SaveAs([ref]$args[1],[ref]17);$d.Close($false)}"
        "finally{$w.Quit()}"
    )
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps, os.path.abspath(src), out],
            capture_output=True, timeout=120, creationflags=0x08000000,
        )
        return r.returncode == 0 and os.path.exists(out)
    except Exception:  # noqa: BLE001
        return False


def _try_libreoffice(src: str, out: str) -> bool:
    exe = shutil.which("soffice") or shutil.which("libreoffice")
    if not exe and sys.platform == "win32":
        for base in (os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")):
            cand = os.path.join(base, "LibreOffice", "program", "soffice.exe")
            if os.path.exists(cand):
                exe = cand
                break
    if not exe:
        return False
    with tempfile.TemporaryDirectory() as td:
        try:
            subprocess.run(
                [exe, "--headless", "--convert-to", "pdf", "--outdir", td, os.path.abspath(src)],
                capture_output=True, timeout=180,
                creationflags=0x08000000 if sys.platform == "win32" else 0,
            )
        except Exception:  # noqa: BLE001
            return False
        produced = os.path.join(td, os.path.splitext(os.path.basename(src))[0] + ".pdf")
        if os.path.exists(produced):
            shutil.move(produced, out)
            return True
    return False


def _find_font() -> tuple[str | None, str | None]:
    """(regular, bold) de una fuente TrueType con buena cobertura Unicode."""
    candidates = [
        (r"C:\Windows\Fonts\segoeui.ttf", r"C:\Windows\Fonts\segoeuib.ttf"),
        (r"C:\Windows\Fonts\arial.ttf", r"C:\Windows\Fonts\arialbd.ttf"),
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
        ("/Library/Fonts/Arial.ttf", "/Library/Fonts/Arial Bold.ttf"),
    ]
    for reg, bold in candidates:
        if os.path.exists(reg):
            return reg, (bold if os.path.exists(bold) else reg)
    return None, None


def _lines_to_pdf(lines: list[tuple[str, str]], out: str, title: str = "") -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from xml.sax.saxutils import escape

    reg, bold = _find_font()
    body_font, bold_font = "Helvetica", "Helvetica-Bold"
    if reg:
        try:
            pdfmetrics.registerFont(TTFont("DW-Regular", reg))
            pdfmetrics.registerFont(TTFont("DW-Bold", bold or reg))
            body_font, bold_font = "DW-Regular", "DW-Bold"
        except Exception:  # noqa: BLE001
            pass
    body = ParagraphStyle("body", fontName=body_font, fontSize=11, leading=15)
    h1 = ParagraphStyle("h1", parent=body, fontName=bold_font, fontSize=20, leading=26, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=body, fontName=bold_font, fontSize=15, leading=20, spaceAfter=4)
    h3 = ParagraphStyle("h3", parent=body, fontName=bold_font, fontSize=12.5, leading=17)
    story = []
    for style, text in lines:
        if not text.strip():
            story.append(Spacer(1, 8))
            continue
        s = body
        sl = style.lower()
        if sl.startswith("title") or sl == "heading 1":
            s = h1
        elif sl == "heading 2":
            s = h2
        elif sl.startswith("heading"):
            s = h3
        story.append(Paragraph(escape(text).replace("\t", "&nbsp;" * 4).replace("  ", "&nbsp; "), s))
    if not story:
        story.append(Paragraph(" ", body))
    SimpleDocTemplate(
        out, pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.2 * cm, bottomMargin=2.2 * cm, title=title,
    ).build(story)


def docx_to_pdf(src: str) -> list[str]:
    out = output_path(src, ".pdf")
    if _try_word(src, out) or _try_libreoffice(src, out):
        return [out]
    # Respaldo sin programas externos: solo texto y títulos (sin imágenes ni formato fino)
    _lines_to_pdf(_docx_lines(src), out, title=os.path.splitext(os.path.basename(src))[0])
    return [out]


# --------------------------------------------------------------------- TEXTO
def _read_text(src: str) -> str:
    with open(src, "rb") as fh:
        raw = fh.read()
    for enc in ("utf-8-sig", "utf-16", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def txt_to_pdf(src: str) -> list[str]:
    out = output_path(src, ".pdf")
    lines = [("", ln.rstrip("\r")) for ln in _read_text(src).split("\n")]
    _lines_to_pdf(lines, out, title=os.path.splitext(os.path.basename(src))[0])
    return [out]


def txt_to_docx(src: str) -> list[str]:
    from docx import Document

    out = output_path(src, ".docx")
    doc = Document()
    for ln in _read_text(src).split("\n"):
        doc.add_paragraph(ln.rstrip("\r"))
    doc.save(out)
    return [out]


# ------------------------------------------------------------------ despacho
def convert(src: str, fmt: str) -> list[str]:
    """Convierte `src` al formato `fmt` ('PNG', 'PDF', 'DOCX', ...). Devuelve las copias creadas."""
    fmt = fmt.upper()
    if not os.path.isfile(src):
        raise ConvertError("El archivo ya no existe.")
    kind = kind_of(src)
    if kind == "image":
        if fmt == "PDF":
            return image_to_pdf(src)
        if fmt == "DOCX":
            return image_to_docx(src)
        return image_to_image(src, fmt)
    if kind == "pdf":
        if fmt in ("PNG", "JPG", "WEBP", "BMP", "TIFF", "HEIC", "AVIF", "GIF"):
            return pdf_to_images(src, fmt)
        if fmt == "TXT":
            return pdf_to_txt(src)
        if fmt == "DOCX":
            return pdf_to_docx(src)
    if kind == "docx":
        if fmt == "PDF":
            return docx_to_pdf(src)
        if fmt == "TXT":
            return docx_to_txt(src)
    if kind == "text":
        if fmt == "PDF":
            return txt_to_pdf(src)
        if fmt == "DOCX":
            return txt_to_docx(src)
    raise ConvertError(f"No sé convertir este archivo a {fmt}.")
