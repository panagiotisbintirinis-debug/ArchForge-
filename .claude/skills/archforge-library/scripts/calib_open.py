"""Open a Home Designer catalog (.calib or .calibz) read-only, on any OS.

Thin re-export of ``archforge.library.hd_calib`` so the skill scripts and the
ArchForge importer share one implementation.
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[4]))
from archforge.library.hd_calib import SQLITE_MAGIC, connect_ro, open_catalog, resolve  # noqa: E402,F401
