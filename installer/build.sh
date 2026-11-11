#!/usr/bin/env bash
# Reconstruye DropWheel-Setup.exe desde Linux. Requiere: micromamba, pip, makensis (nsis).
# Uso: installer/build.sh  (deja el instalador en dist/DropWheel-Setup.exe)
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
B="${BUILD:-/tmp/dropwheel-build}"
rm -rf "$B" && mkdir -p "$B/DropWheel/app" "$HERE/dist"

# 1) Python 3.12 para Windows (con tkinter) desde conda-forge
export MAMBA_ROOT_PREFIX="$B/mamba"
micromamba create -y -q -p "$B/DropWheel/python" --platform win-64 -c conda-forge --override-channels python=3.12 tk
# 2) Librerías (ruedas de Windows)
pip install -q --target "$B/DropWheel/python/Lib/site-packages" --platform win_amd64 --python-version 3.12 \
    --implementation cp --only-binary=:all: --no-compile -r "$HERE/requirements-win.txt"
# 3) Recorte de lo que no se usa
P="$B/DropWheel/python"
rm -rf "$P"/{Lib/test,Lib/idlelib,Lib/turtledemo,Lib/lib2to3,Tools,Scripts,conda-meta,include,libs} \
       "$P"/Library/{include,share} "$P"/Library/lib/{cmake,pkgconfig} "$P"/Library/lib/*.lib 2>/dev/null || true
rm -rf "$P"/Lib/site-packages/{share,Xlib,python_xlib-*,cv2/data} "$P"/Lib/site-packages/cv2/opencv_videoio_ffmpeg*.dll \
       "$P"/Lib/site-packages/*.whl 2>/dev/null || true
find "$B" -name __pycache__ -prune -exec rm -rf {} \;
cp "$HERE/installer/sitecustomize.py" "$P/Lib/site-packages/sitecustomize.py"
cp "$P/pythonw.exe" "$P/DropWheel.exe"   # el proceso aparece como DropWheel.exe en el Administrador de tareas
# 4) La app
cp -r "$HERE/dropwheel" "$HERE/DropWheel.pyw" "$HERE/README.md" "$B/DropWheel/app/"
find "$B/DropWheel/app" -name __pycache__ -prune -exec rm -rf {} \;
python3 -c "import sys; sys.path.insert(0,'$HERE'); from dropwheel.icon import save_ico; save_ico('$B/DropWheel/dropwheel.ico')"
# 5) Instalador
makensis -V2 -DBUILDDIR="$B/DropWheel" -DOUTFILE="$HERE/dist/DropWheel-Setup.exe" "$HERE/installer/DropWheel.nsi"
ls -la "$HERE/dist"
