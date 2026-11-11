"""Nombres de salida: siempre una copia nueva, nunca se pisa el original."""
from __future__ import annotations

import os


def unique_path(folder: str, stem: str, ext: str) -> str:
    """folder/stem.ext, o 'stem (1).ext', 'stem (2).ext'... si ya existe."""
    candidate = os.path.join(folder, stem + ext)
    n = 1
    while os.path.exists(candidate):
        candidate = os.path.join(folder, f"{stem} ({n}){ext}")
        n += 1
    return candidate


def output_path(src: str, ext: str, suffix: str = "") -> str:
    folder, name = os.path.split(os.path.abspath(src))
    stem = os.path.splitext(name)[0]
    return unique_path(folder, stem + suffix, ext)
