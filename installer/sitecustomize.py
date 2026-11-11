"""DropWheel: hace que el Python incluido encuentre Tcl/Tk y sus DLL sin depender de variables de entorno."""
import os
import sys

_root = os.path.dirname(os.path.abspath(sys.executable))
_lib = os.path.join(_root, "Library", "lib")
for _name, _var in (("tcl8.6", "TCL_LIBRARY"), ("tk8.6", "TK_LIBRARY")):
    _p = os.path.join(_lib, _name)
    if os.path.isdir(_p):
        os.environ.setdefault(_var, _p)
_bin = os.path.join(_root, "Library", "bin")
if os.path.isdir(_bin):
    os.environ["PATH"] = _bin + os.pathsep + os.environ.get("PATH", "")
    try:
        os.add_dll_directory(_bin)
    except (AttributeError, OSError):
        pass
