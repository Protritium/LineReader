import tempfile
import unittest
import zipfile
from pathlib import Path
from epub_reader import read_epub
from reader_core import LineReader


class EpubTests(unittest.TestCase):
    def make_book(self, directory, version=3, encrypted=False, toc=True):
        path = Path(directory) / "中文书籍.epub"
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("META-INF/container.xml", '<container><rootfiles><rootfile full-path="OPS/book.opf"/></rootfiles></container>')
            nav = '<item id="nav" href="nav.xhtml" properties="nav" media-type="application/xhtml+xml"/>' if version == 3 else '<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>'
            z.writestr("OPS/book.opf", '<package><manifest><item id="b" href="second.xhtml" media-type="application/xhtml+xml"/><item id="a" href="first.xhtml" media-type="application/xhtml+xml"/>' + (nav if toc else '') + '</manifest><spine toc="ncx"><itemref idref="a"/><itemref idref="b"/></spine></package>')
            z.writestr("OPS/first.xhtml", '<html><head><title>不应显示</title><style>隐藏样式</style></head><body><h1 id="one">第一章</h1><p>你好<b>世界</b>。</p><h2 id="two">第二章</h2><p>继续阅读。</p></body></html>')
            z.writestr("OPS/second.xhtml", '<html><body><h1>第三章</h1><p>最后一章。</p></body></html>')
            if toc and version == 3:
                z.writestr("OPS/nav.xhtml", '<html xmlns:epub="http://www.idpf.org/2007/ops"><body><nav epub:type="toc"><ol><li><a href="first.xhtml#one">第一章目录名</a></li><li><a href="first.xhtml#two">第二章目录名</a></li><li><a href="second.xhtml">第三章目录名</a></li></ol></nav></body></html>')
            elif toc:
                z.writestr("OPS/toc.ncx", '<ncx><navMap><navPoint><navLabel><text>第一章目录名</text></navLabel><content src="first.xhtml#one"/></navPoint><navPoint><navLabel><text>第二章目录名</text></navLabel><content src="first.xhtml#two"/></navPoint></navMap></ncx>')
            if encrypted:
                z.writestr("META-INF/encryption.xml", '<encryption><CipherReference URI="OPS/first.xhtml"/></encryption>')
        return path

    def test_epub2_and_3_order_and_anchor_positions(self):
        for version in (2, 3):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as d:
                text, chapters = read_epub(self.make_book(d, version))
                self.assertLess(text.index("第一章"), text.index("第三章"))
                self.assertIn("你好世界。", text)
                self.assertNotIn("不应显示", text)
                self.assertNotIn("隐藏样式", text)
                self.assertEqual(chapters[1][0], "第二章目录名")
                book = LineReader(text)
                self.assertEqual(book.text, text)
                book.seek(chapters[1][1])
                self.assertEqual(book.line(80, len), "第二章")
                book.seek_percent(100, 80, len)
                self.assertTrue(book.line(80, len))

    def test_no_toc_falls_back_to_spine(self):
        with tempfile.TemporaryDirectory() as d:
            text, chapters = read_epub(self.make_book(d, toc=False))
            self.assertEqual([t for t, _ in chapters], ["第一章", "第三章"])

    def test_encrypted_and_invalid_archives(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(ValueError, "DRM"):
                read_epub(self.make_book(d, encrypted=True))
            path = Path(d) / "bad.epub"
            path.write_bytes(b"not a zip")
            with self.assertRaisesRegex(ValueError, "无法解析"):
                read_epub(path)


if __name__ == "__main__":
    unittest.main()
