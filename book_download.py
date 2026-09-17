"""Download a user-selected public TXT URL; no site-specific endpoint assumptions."""
import re
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from reader_core import decode_text

MAX_BYTES = 30 * 1024 * 1024


def download_text(url):
    url = url.strip()
    if urlsplit(url).scheme not in ("http", "https") or not urlsplit(url).hostname:
        raise ValueError("请填写完整的 http 或 https 下载链接。")
    request = Request(url, headers={"User-Agent": "LineReader/1.2.0", "Accept": "text/plain, application/octet-stream"})
    with urlopen(request, timeout=25) as response:
        if urlsplit(response.url).scheme not in ("http", "https"):
            raise ValueError("不支持此重定向地址。")
        data = response.read(MAX_BYTES + 1)
        content_type = response.headers.get_content_type()
    if len(data) > MAX_BYTES:
        raise ValueError("文件超过 30 MB，请通过浏览器下载后手动打开。")
    if not data:
        raise ValueError("下载结果为空。")
    text, encoding = decode_text(data)
    if content_type in ("text/html", "application/xhtml+xml") or re.search(r"<!doctype\s+html|<html\b|<head\b|<body\b", text[:2048], re.I):
        raise ValueError("该链接返回的是网页或验证页，不是 TXT 文件。请在浏览器打开下载页面，复制实际 TXT 下载链接。")
    if not text.strip() or any(ord(c) < 9 or 13 < ord(c) < 32 for c in text[:8192]):
        raise ValueError("下载结果不是可识别的纯文本，可能是压缩包或其他文件。")
    return text, encoding


def save_download(directory, title, text):
    directory.mkdir(parents=True, exist_ok=True)
    name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")[:100] or "下载小说"
    if name.lower().endswith(".txt"):
        name = name[:-4]
    if re.fullmatch(r"CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9]", name, re.I):
        name = "小说_" + name
    for index in range(10000):
        path = directory / f"{name}{' (' + str(index) + ')' if index else ''}.txt"
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(text)
            return path
        except FileExistsError:
            continue
    raise ValueError("同名文件过多，请更换书名。")
