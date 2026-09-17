"""Z-Library HTML adapter based on the user-provided saved book page."""
from html.parser import HTMLParser
from http.cookiejar import CookieJar
from urllib.parse import quote, urljoin, urlsplit
from urllib.request import Request, build_opener, HTTPCookieProcessor
import io
import re
import zipfile
from pathlib import Path
from epub_reader import read_epub
from book_download import save_download
from reader_core import decode_text
from urllib.error import HTTPError

BASE = "https://z-library.sk"
MIRRORS = (BASE, "https://zh.zlib.bz", "https://zlib.bz", "https://z-lib.sk")


def site_url(url, base=BASE):
    url = urljoin(base, url)
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.hostname not in {urlsplit(m).hostname for m in MIRRORS} or parsed.username or parsed.port not in (None, 443):
        raise ValueError("请使用列表中站点的 HTTPS 书籍链接。")
    return quote(url, safe=":/?=&%+#")


class Page(HTMLParser):
    def __init__(self, html, base=BASE):
        super().__init__(convert_charrefs=True)
        self.books = []
        self.downloads = []
        self.title = ""
        self.in_title = False
        self.link = None
        self.base = base
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        href = attrs.get("href", "")
        if tag == "a":
            self.link = [href, []]
            if "/dl/" in href and "dlButton" in attrs.get("class", ""):
                self.downloads.append(site_url(href, self.base))
        if tag == "z-bookcard" and href:
            name = attrs.get("title") or attrs.get("name")
            if name and "/book/" in href:
                self.books.append((name, site_url(href, self.base)))

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.link:
            self.link[1].append(data)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag == "a" and self.link:
            href, parts = self.link
            title = re.sub(r"\s+", " ", "".join(parts)).strip()
            if title and "/book/" in href:
                try:
                    item = (title, site_url(href, self.base))
                    if not any(url == item[1] for _, url in self.books):
                        self.books.append(item)
                except ValueError:
                    pass
            self.link = None


class ZLibrary:
    def __init__(self, base=BASE):
        self.base = site_url(base).rstrip("/")
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(self, url, limit=32 * 1024 * 1024):
        request = Request(site_url(url, self.base), headers={"User-Agent": "Mozilla/5.0 LineReader/1.4.1", "Referer": self.base + "/"})
        try:
            response = self.opener.open(request, timeout=25)
        except HTTPError as exc:
            body = exc.read(65536)
            exc.close()
            if b"checking your browser" in body.lower() or b"captcha" in body.lower():
                raise ValueError("站点要求浏览器验证，当前直连无法搜索或下载；请切换镜像。浏览器验证状态不会自动同步到程序。") from exc
            raise ValueError(f"站点返回 HTTP {exc.code}，请更换镜像或稍后重试。") from exc
        with response:
            data = response.read(limit + 1)
            if len(data) > limit:
                raise ValueError("响应超过 32 MB，请使用浏览器下载后导入。")
            if b"checking your browser" in data[:65536].lower():
                raise ValueError("站点返回浏览器验证页，请切换镜像。")
            return data, response.headers.get_content_type(), response.url

    def search(self, keyword):
        if not keyword.strip():
            raise ValueError("请输入书名。")
        data, _, final = self.request(self.base + "/s/" + quote(keyword.strip(), safe=""))
        page = Page(data.decode("utf-8-sig"), final or self.base)
        if not page.books:
            raise ValueError("未解析到搜索结果：可能没有匹配书籍，或网站要求登录、验证码，或页面结构已变化。")
        return page.books

    def details(self, url):
        data, _, final = self.request(url)
        page = Page(data.decode("utf-8-sig"), final or url)
        if not page.downloads:
            raise ValueError("页面未提供直接下载按钮，可能需要登录、验证或已达到下载限额。请在浏览器检查该书页。")
        title = page.title.split("|")[0].strip() or "下载小说"
        return title, page.downloads[0]

    def download(self, book_url, directory):
        title, url = self.details(book_url)
        data, content_type, _ = self.request(url)
        is_epub = zipfile.is_zipfile(io.BytesIO(data))
        if not is_epub and (content_type in ("text/html", "application/xhtml+xml") or re.search(br"<html\b|<!doctype\s+html", data[:2048], re.I)):
            raise ValueError("下载入口返回了网页，可能需要登录、验证或下载额度不足；没有保存为电子书。")
        if is_epub:
            read_epub(io.BytesIO(data))  # Validate before persisting, including DRM handling.
            directory.mkdir(parents=True, exist_ok=True)
            name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", title).strip(" .")[:90] or "小说"
            name = "电子书_" + name
            for index in range(10000):
                path = directory / f"{name}{'_' + str(index) if index else ''}.epub"
                try:
                    with path.open("xb") as stream:
                        stream.write(data)
                    return path
                except FileExistsError:
                    continue
            raise ValueError("同名文件过多。")
        if content_type == "application/pdf" or data.startswith(b"%PDF"):
            raise ValueError("该版本为 PDF，阅读器目前支持 TXT 和 EPUB。")
        text, _ = decode_text(data)
        if not text.strip() or any(ord(c) < 9 or 13 < ord(c) < 32 for c in text[:8192]):
            raise ValueError("下载结果不是支持的 TXT / EPUB。")
        return save_download(directory, title, text)
