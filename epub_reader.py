"""Read EPUB 2/3 text and navigation without extracting archive files."""
import posixpath
import re
from html.parser import HTMLParser
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET
import zipfile

MAX_MEMBER = 16 * 1024 * 1024
MAX_TEXT = 64 * 1024 * 1024


def local(tag):
    return tag.rsplit("}", 1)[-1]


def resolve(base, href):
    parts = urlsplit(href)
    if parts.scheme or parts.netloc:
        raise ValueError("EPUB 包含外部正文链接，无法离线读取。")
    path = posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(parts.path))) if parts.path else base
    if path.startswith(("../", "/")) or path == ".." or "\\" in path:
        raise ValueError("EPUB 内部路径无效。")
    return path, unquote(parts.fragment)


class TextParser(HTMLParser):
    blocks = {"p", "div", "section", "article", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "tr", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.size = 0
        self.anchors = {}
        self.ignored = []

    def append(self, text):
        self.parts.append(text)
        self.size += len(text)

    def newline(self):
        if self.parts and not self.parts[-1].endswith("\n"):
            self.append("\n")

    def handle_starttag(self, tag, attrs):
        if tag in {"head", "script", "style", "rt", "rp"}:
            self.ignored.append(tag)
        if self.ignored:
            return
        if tag in self.blocks:
            self.newline()
        for key, value in attrs:
            if key in ("id", "name") and value:
                self.anchors[value] = self.size

    def handle_endtag(self, tag):
        if self.ignored:
            if tag == self.ignored[-1]:
                self.ignored.pop()
            return
        if tag in self.blocks:
            self.newline()

    def handle_data(self, data):
        if not self.ignored:
            value = re.sub(r"\s+", " ", data).replace("\x00", "").replace("\ufeff", "")
            if value.strip():
                self.append(value)


def read_epub(path):
    """Return normalized plain text and (title, character offset) chapters."""
    try:
        with zipfile.ZipFile(path) as archive:
            consumed = 0

            def read(name):
                nonlocal consumed
                info = archive.getinfo(name)
                consumed += info.file_size
                if info.file_size > MAX_MEMBER or consumed > MAX_TEXT:
                    raise ValueError("EPUB 正文或目录过大，超出读取限制。")
                return archive.read(name)

            def xml(name):
                data = read(name)
                if b"<!ENTITY" in data.upper():
                    raise ValueError("EPUB XML 包含不支持的实体声明。")
                return ET.fromstring(data)

            container = xml("META-INF/container.xml")
            roots = [e for e in container.iter() if local(e.tag) == "rootfile"]
            if not roots:
                raise ValueError("EPUB 缺少书籍索引。")
            opf, _ = resolve("", roots[0].get("full-path", ""))
            package = xml(opf)
            manifest = {e.get("id"): e for e in package.iter() if local(e.tag) == "item"}
            spine = next((e for e in package.iter() if local(e.tag) == "spine"), None)
            if spine is None:
                raise ValueError("EPUB 缺少正文阅读顺序。")
            encrypted = set()
            if "META-INF/encryption.xml" in archive.namelist():
                encrypted = {resolve("", e.get("URI", ""))[0] for e in xml("META-INF/encryption.xml").iter() if local(e.tag) == "CipherReference"}
            chunks, positions, fallback = [], {}, []
            length = 0
            for ref in spine:
                if local(ref.tag) != "itemref" or ref.get("linear") == "no":
                    continue
                item = manifest.get(ref.get("idref"))
                if item is None:
                    raise ValueError("EPUB 正文索引引用了不存在的文件。")
                if "nav" in item.get("properties", "").split():
                    continue
                if item.get("media-type") not in ("application/xhtml+xml", "text/html"):
                    continue
                name, _ = resolve(opf, item.get("href", ""))
                if name in encrypted:
                    raise ValueError("此 EPUB 正文受 DRM 加密，暂不支持读取。")
                raw = read(name)
                if raw.startswith((b"\xff\xfe", b"\xfe\xff")):
                    source = raw.decode("utf-16")
                else:
                    declaration = re.search(br'encoding=[\'"]([^\'"]+)', raw[:200])
                    source = raw.decode(declaration[1].decode("ascii") if declaration else "utf-8-sig")
                parser = TextParser()
                parser.feed(source)
                parser.close()
                text = "".join(parser.parts)
                if not text.strip():
                    continue
                positions[(name, "")] = length
                for anchor, offset in parser.anchors.items():
                    positions[(name, anchor)] = length + offset
                title = next((line.strip() for line in text.splitlines() if line.strip()), "章节")[:100]
                fallback.append((title, length))
                chunks.append(text + "\n")
                length += len(text) + 1
            text = "".join(chunks)
            if not text.strip():
                raise ValueError("EPUB 中没有可读取的文字，可能是扫描图片书。")
            entries = []
            nav = next((item for item in manifest.values() if "nav" in item.get("properties", "").split()), None)
            if nav is not None:
                name, _ = resolve(opf, nav.get("href", ""))
                document = xml(name)
                toc = next((e for e in document.iter() if local(e.tag) == "nav" and any(local(k) == "type" and "toc" in v.split() for k, v in e.attrib.items())), None)
                if toc is not None:
                    entries = [("".join(e.itertext()).strip(), name, e.get("href")) for e in toc.iter() if local(e.tag) == "a" and e.get("href")]
            if not entries:
                ncx = manifest.get(spine.get("toc"))
                if ncx is None:
                    ncx = next((item for item in manifest.values() if item.get("media-type") == "application/x-dtbncx+xml"), None)
                if ncx is not None:
                    name, _ = resolve(opf, ncx.get("href", ""))
                    for point in xml(name).iter():
                        if local(point.tag) != "navPoint":
                            continue
                        label = next((e for e in point if local(e.tag) == "navLabel"), None)
                        content = next((e for e in point if local(e.tag) == "content"), None)
                        if label is not None and content is not None:
                            entries.append(("".join(label.itertext()).strip(), name, content.get("src", "")))
            chapters, seen = [], set()
            for title, base, href in entries:
                key = resolve(base, href)
                offset = positions.get(key, positions.get((key[0], "")))
                if title and offset is not None and offset not in seen:
                    chapters.append((re.sub(r"\s+", " ", title), offset))
                    seen.add(offset)
            return text, sorted(chapters or fallback, key=lambda entry: entry[1])
    except (zipfile.BadZipFile, KeyError, ET.ParseError, UnicodeError, LookupError, RuntimeError) as exc:
        raise ValueError(f"无法解析 EPUB：{exc}") from exc
