"""Open the system browser and detect completed new book downloads."""
import os
from pathlib import Path
import shutil
import subprocess
import time
import webbrowser


def open_browser(url):
    candidates = [shutil.which("msedge")]
    if os.name == "nt":
        for key in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(key)
            if base:
                candidates.append(str(Path(base) / "Microsoft/Edge/Application/msedge.exe"))
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                subprocess.Popen([candidate, "--app=" + url, "--window-size=1000,760"])
                return "已打开 Edge 独立小窗口；请在窗口中完成验证和下载。"
    if not webbrowser.open(url):
        raise OSError("无法打开浏览器，请检查默认浏览器设置。")
    return "已打开默认浏览器；请完成验证和下载。"


class DownloadWatch:
    def __init__(self, directory, clock=time.monotonic):
        self.directory = Path(directory)
        self.clock = clock
        self.baseline = self.snapshot()
        self.pending = {}

    def snapshot(self):
        result = {}
        for path in self.directory.iterdir():
            if path.suffix.lower() in (".epub", ".txt") and path.is_file():
                try:
                    stat = path.stat()
                    result[path] = (stat.st_size, stat.st_mtime_ns)
                except OSError:
                    continue
        return result

    def poll(self):
        now = self.clock()
        files = self.snapshot()
        ready = []
        for path, signature in files.items():
            if signature == self.baseline.get(path) or not signature[0]:
                continue
            if any(Path(str(path) + suffix).exists() for suffix in (".crdownload", ".part", ".tmp")):
                self.pending.pop(path, None)
                continue
            previous = self.pending.get(path)
            if previous is None or previous[0] != signature:
                self.pending[path] = (signature, now)
            elif now - previous[1] >= 3:
                try:
                    with path.open("rb") as stream:
                        stream.read(1)
                except OSError:
                    continue
                ready.append(path)
                self.baseline[path] = signature
                self.pending.pop(path, None)
        for path in list(self.pending):
            if path not in files:
                self.pending.pop(path)
        return ready
