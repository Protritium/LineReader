"""Persistent, content-addressed copies of imported books."""
import hashlib
from pathlib import Path
import shutil


def import_book(source, directory):
    source, directory = Path(source), Path(directory)
    suffix = source.suffix.lower()
    if suffix not in (".txt", ".epub"):
        raise ValueError("书架支持 TXT 和 EPUB 文件。")
    with source.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest() if hasattr(hashlib, "file_digest") else hashlib.sha256(stream.read()).hexdigest()
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / (digest + suffix)
    if source.resolve() != target.resolve() and not target.exists():
        temporary = target.with_suffix(suffix + ".tmp")
        try:
            shutil.copyfile(source, temporary)
            temporary.replace(target)
        finally:
            if temporary.exists():
                temporary.unlink()
    return digest + suffix, target


def horizontal_family(name):
    return name.lstrip("@").strip()


VERTICAL_PUNCTUATION = str.maketrans({
    "︐": "，", "︑": "、", "︒": "。", "︓": "：", "︔": "；", "︕": "！", "︖": "？",
    "︵": "（", "︶": "）", "︷": "{", "︸": "}", "︹": "〔", "︺": "〕",
    "︻": "【", "︼": "】", "︽": "《", "︾": "》", "︿": "〈", "﹀": "〉",
    "﹁": "「", "﹂": "」", "﹃": "『", "﹄": "』", "﹇": "［", "﹈": "］",
    "︙": "…", "︱": "—", "︲": "–", "︳": "_", "︴": "_",
})


def horizontal_text(text):
    return text.translate(VERTICAL_PUNCTUATION)
