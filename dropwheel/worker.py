"""Proceso de trabajo: hace la conversión/acción y imprime UNA línea JSON con el resultado.

Uso:  python -m dropwheel.worker convert FORMATO archivo [archivo ...]
      python -m dropwheel.worker action ACCION archivo
El proceso residente lo lanza y se cierra al terminar, así la RAM vuelve al sistema.
"""
from __future__ import annotations

import json
import sys
import traceback


def _emit(**data) -> None:
    sys.stdout.write(json.dumps(data, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _convert(fmt: str, files: list[str]) -> int:
    from .engine.convert import ConvertError, convert

    outs, errors = [], []
    for f in files:
        try:
            outs.extend(convert(f, fmt))
        except ConvertError as e:
            errors.append(f"{f}: {e}")
        except Exception as e:  # noqa: BLE001
            errors.append(f"{f}: {e}")
            traceback.print_exc()
    if outs:
        _emit(ok=True, outputs=outs, error="; ".join(errors) if errors else None)
        return 0
    _emit(ok=False, error="; ".join(errors) or "No se creó ningún archivo.")
    return 1


def _action(name: str, path: str) -> int:
    name = name.upper()
    try:
        if name == "CROP":
            from .ui import crop as m
        elif name == "ADD BG":
            from .ui import addbg as m
        elif name == "EDIT":
            from .ui import editor as m
        elif name == "ANNOTATE":
            from .ui import annotate as m
        elif name == "REDACT":
            from .ui import annotate as m0

            class m:  # noqa: N801
                run = staticmethod(lambda p: m0.run(p, redact=True))
        elif name == "COMPRESS":
            from .ui import compress as m
        elif name == "METADATA":
            from .ui import metadata as m
        else:
            _emit(ok=False, error=f"Acción desconocida: {name}")
            return 2
        out = m.run(path)
    except Exception as e:  # noqa: BLE001
        traceback.print_exc()
        _emit(ok=False, error=str(e))
        return 1
    if out:
        _emit(ok=True, outputs=[out])
    else:
        _emit(ok=False, cancelled=True)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 3:
        _emit(ok=False, error="Uso: worker convert FORMATO archivo... | worker action ACCION archivo")
        return 2
    if argv[0] == "convert":
        return _convert(argv[1], argv[2:])
    if argv[0] == "action":
        return _action(argv[1], argv[2])
    _emit(ok=False, error=f"Comando desconocido: {argv[0]}")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
