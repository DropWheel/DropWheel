"""Configuración del usuario en %APPDATA%\\DropWheel\\settings.json (liviano, sin dependencias)."""
from __future__ import annotations

import json
import os

DEFAULTS = {
    "enabled": True,
    "trigger": "shift",            # "shift" | "ctrl" | "alt"
    "size": 0.85,                  # 1.0 = tamaño grande; 0.7 = compacto
    "style": "auto",               # "auto" (según el fondo) | "dark" | "light"
    "accent": "auto",              # "auto" (color más vivo del fondo) | "system" (color de Windows) | "#RRGGBB"
    "glass": True,                 # vidrio esmerilado con lo que hay detrás (False = color liso)
    "animations": True,            # fundido de entrada
    "require_drag_image": True,    # exige que Windows esté mostrando la miniatura de arrastre (evita falsos positivos)
    "extra_window_classes": [],    # clases de ventana extra donde activar la rueda (otros exploradores de archivos)
    "any_window": False,           # True = activar la rueda sobre cualquier programa
    "reveal_in_explorer": False,   # abrir el Explorador con el archivo nuevo seleccionado
    "notify": True,                # avisar con un globo en la bandeja cuando termina
}


def config_dir() -> str:
    base = os.environ.get("APPDATA") or os.path.expanduser("~")
    path = os.path.join(base, "DropWheel")
    os.makedirs(path, exist_ok=True)
    return path


def _file() -> str:
    return os.path.join(config_dir(), "settings.json")


def load() -> dict:
    data = dict(DEFAULTS)
    try:
        with open(_file(), "r", encoding="utf-8") as f:
            data.update({k: v for k, v in json.load(f).items() if k in DEFAULTS})
    except (OSError, ValueError):
        pass
    return data


def save(data: dict) -> None:
    try:
        with open(_file(), "w", encoding="utf-8") as f:
            json.dump({k: data.get(k, v) for k, v in DEFAULTS.items()}, f, indent=2, ensure_ascii=False)
    except OSError:
        pass
