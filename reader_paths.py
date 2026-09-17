"""Keep installed resources separate from persistent user data."""
import os
from pathlib import Path
import sys


def novel_files(directory):
    """Ignore project metadata when discovering user-supplied TXT books."""
    excluded = {"requirements.txt", "sha256sums.txt", "readme.txt", "license.txt"}
    if not Path(directory).is_dir():
        return []
    return sorted((p for p in Path(directory).iterdir()
                   if p.is_file() and p.suffix.casefold() in (".txt", ".epub")
                   and p.name.casefold() not in excluded), key=lambda p: p.name.casefold())


def state_path(platform=None, environ=None, home=None, base=None):
    platform = sys.platform if platform is None else platform
    environ = os.environ if environ is None else environ
    home = Path.home() if home is None else Path(home)
    base = Path(__file__).resolve().parent if base is None else Path(base)
    if platform == "win32":
        return Path(environ.get("LOCALAPPDATA") or home / "AppData" / "Local") / "LineReader" / "state.json"
    return base / ".reader_state.json"


BASE = Path(__file__).resolve().parent
BOOKS = BASE / "books" if getattr(sys, "frozen", False) else BASE
STATE = state_path()
