"""Qué opciones muestra la rueda según el tipo de archivo.

Este módulo es liviano a propósito: lo importa el proceso residente.
"""
from __future__ import annotations

import os

IMAGE_EXTS = {
    ".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff",
    ".heic", ".heif", ".avif", ".gif",
}
PDF_EXTS = {".pdf"}
DOC_EXTS = {".docx"}
TEXT_EXTS = {".txt", ".md", ".log", ".csv"}

# Formatos de salida (etiqueta -> extensión)
FORMAT_EXT = {
    "PNG": ".png", "JPG": ".jpg", "WEBP": ".webp", "HEIC": ".heic",
    "AVIF": ".avif", "BMP": ".bmp", "TIFF": ".tiff", "GIF": ".gif",
    "PDF": ".pdf", "DOCX": ".docx", "TXT": ".txt",
}

# Acciones disponibles para imágenes (orden = sentido horario desde arriba)
IMAGE_ACTIONS = ["COMPRESS", "METADATA", "EDIT", "ANNOTATE", "ADD BG", "CROP", "REDACT"]
PDF_ACTIONS = ["COMPRESS", "METADATA"]
ACTION_LABEL = {
    "COMPRESS": "Compress", "METADATA": "Metadata", "EDIT": "Edit",
    "ANNOTATE": "Annotate", "ADD BG": "Add BG", "CROP": "Crop", "REDACT": "Redact",
}


def kind_of(path: str) -> str | None:
    """'image' | 'pdf' | 'docx' | 'text' | None si no se soporta."""
    ext = os.path.splitext(path)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOC_EXTS:
        return "docx"
    if ext in TEXT_EXTS:
        return "text"
    return None


def formats_for(path: str) -> list[str]:
    """Formatos de destino ofrecidos (sin incluir el formato actual)."""
    kind = kind_of(path)
    ext = os.path.splitext(path)[1].lower()
    if kind == "image":
        opts = ["PNG", "JPG", "WEBP", "HEIC", "AVIF", "TIFF", "BMP", "PDF", "DOCX"]
    elif kind == "pdf":
        opts = ["DOCX", "JPG", "PNG", "TXT"]
    elif kind == "docx":
        opts = ["PDF", "TXT"]
    elif kind == "text":
        opts = ["PDF", "DOCX"]
    else:
        return []
    same = {".jpeg": ".jpg", ".tif": ".tiff", ".heif": ".heic"}.get(ext, ext)
    return [o for o in opts if FORMAT_EXT[o] != same]


def actions_for(path: str) -> list[str]:
    kind = kind_of(path)
    if kind == "image":
        return list(IMAGE_ACTIONS)
    if kind == "pdf":
        return list(PDF_ACTIONS)
    return []


def pages_for(path: str) -> dict[str, list[str]]:
    """Páginas de la rueda: 'convert' (formatos) y 'actions' (herramientas)."""
    pages: dict[str, list[str]] = {}
    f = formats_for(path)
    if f:
        pages["convert"] = f
    a = actions_for(path)
    if a:
        pages["actions"] = a
    return pages


def human_size(path: str) -> str:
    try:
        n = os.path.getsize(path)
    except OSError:
        return ""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return ""
