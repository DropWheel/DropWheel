"""Lanzador sin consola: doble clic (o inicio con Windows)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dropwheel.agent import main  # noqa: E402

sys.exit(main())
