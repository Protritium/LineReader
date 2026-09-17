"""Validate offline tools and create the transferable Windows build ZIP."""
import hashlib
from pathlib import Path
import re
import zipfile
from reader_paths import novel_files

ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = {
        "python-3.12.10-amd64.exe": "67b5635e80ea51072b87941312d00ec8927c4db9ba18938f7ad2d27b328b95fb",
        "inno-setup.exe": "9c73c3bae7ed48d44112a0f48e66742c00090bdb5bef71d9d3c056c66e97b732",
    }
    for name, checksum in expected.items():
        if digest(ROOT / "offline-tools" / name) != checksum:
            raise ValueError(f"Installer checksum mismatch: {name}")
    requirements = (ROOT / "offline-tools/requirements.txt").read_text(encoding="utf-8")
    for line in requirements.splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        name, version, checksum = re.fullmatch(r"([\w-]+)==([^ ]+) --hash=sha256:([0-9a-f]{64})", line).groups()
        matches = list((ROOT / "offline-tools/wheels").glob(f"{name.replace('-', '_')}-{version}-*.whl"))
        if len(matches) != 1 or digest(matches[0]) != checksum:
            raise ValueError(f"Wheel checksum mismatch: {name}")
    version = re.search(r'#define MyAppVersion "([^"]+)"', (ROOT / "installer/LineReader.iss").read_text(encoding="utf-8")).group(1)
    names = ["reader.py", "reader_core.py", "reader_paths.py", "windows_mouse.py", "windows_launcher.py", "book_download.py", "download_dialog.py", "test_reader.py",
             "epub_reader.py", "test_epub.py", "zlibrary_source.py", "zlibrary_dialog.py", "test_zlibrary.py", "requirements.txt", "README.md", "LineReader.spec", "BUILD-INSTALLER.cmd",
             "app_info.py", "README.en.md", "bookshelf.py", "test_bookshelf.py", "browser_import.py", "test_browser_import.py", "make_bundle.py", "启动阅读器.bat"]
    paths = [ROOT / name for name in names]
    paths.extend(p for folder in ("offline-tools", "installer") for p in (ROOT / folder).rglob("*") if p.is_file())
    # Public distribution contains code and build tools, never personal books.
    output = ROOT / "releases" / f"LineReader-Windows-build-{version}.zip"
    output.parent.mkdir(exist_ok=True)
    manifest = []
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paths):
            name = path.relative_to(ROOT).as_posix()
            archive.write(path, "LineReader/" + name)
            manifest.append(f"{digest(path)}  {name}")
        archive.writestr("LineReader/SHA256SUMS.txt", "\n".join(manifest) + "\n")
    with zipfile.ZipFile(output) as archive:
        bad = archive.testzip()
        if bad:
            raise ValueError(f"Archive integrity failure: {bad}")
    checksum = digest(output)
    output.with_suffix(".zip.sha256").write_text(f"{checksum}  {output.name}\n", encoding="ascii")
    print(f"Offline tool checks passed; ZIP integrity checked: {len(paths)} files")
    print(f"{output}\n{output.stat().st_size / 1024**2:.1f} MiB\nSHA256: {checksum}")


if __name__ == "__main__":
    main()
