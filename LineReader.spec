# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

root = Path(SPECPATH)
sys.path.insert(0, str(root))
from reader_paths import novel_files

books = []  # Public builds never bundle users' novels.
a = Analysis(
    [str(root / "windows_launcher.py")],
    pathex=[str(root)],
    binaries=[],
    datas=books,
    hiddenimports=["chardet", "tkinter", "tkinter.ttk"],
    hookspath=[], hooksconfig={}, runtime_hooks=[], excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True,
    name="LineReader", debug=False, bootloader_ignore_signals=False,
    strip=False, upx=False, console=False, disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="LineReader")
