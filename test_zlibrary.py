import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from zlibrary_source import Page, ZLibrary, site_url
import test_epub


class ZLibraryTests(unittest.TestCase):
    def test_mirror_relative_links_and_verification(self):
        from urllib.error import HTTPError
        import io
        page = Page('<a href="/book/abc/test.html">Test</a><a class="dlButton" href="/dl/abc">Download</a>', 'https://zh.zlib.bz')
        self.assertEqual(page.books[0][1], 'https://zh.zlib.bz/book/abc/test.html')
        self.assertEqual(page.downloads[0], 'https://zh.zlib.bz/dl/abc')
        client = ZLibrary('https://zh.zlib.bz')
        error = HTTPError('https://zh.zlib.bz', 503, 'Unavailable', {}, io.BytesIO(b'<title>Checking your browser ...</title>'))
        with patch.object(client.opener, 'open', side_effect=error):
            with self.assertRaisesRegex(ValueError, '浏览器验证'):
                client.request('https://zh.zlib.bz/')

    def test_saved_page_structure(self):
        page = Page('<title>我的师妹不可能是傻白甜 | 归山玉 | download on Z-Library</title><a class="btn dlButton addDownloadedBook" href="https://z-library.sk/dl/aBkWR3NMBe">下载</a>')
        self.assertEqual(page.downloads, ["https://z-library.sk/dl/aBkWR3NMBe"])

    def test_search_links_and_unicode(self):
        page = Page('<a href="/book/abc/中文.html"><b>书名</b></a><a href="/book/abc/中文.html">重复</a>')
        self.assertEqual(len(page.books), 1)
        self.assertEqual(page.books[0][0], "书名")
        self.assertIn("%E4%B8%AD", page.books[0][1])
        with self.assertRaises(ValueError):
            site_url("https://example.org/book/abc")

    def test_search_request_and_login_page(self):
        client = ZLibrary()
        with patch.object(client, "request", return_value=(b'<a href="/book/abc/test.html">Test</a>', 'text/html', '')) as request:
            self.assertEqual(client.search("书名")[0][0], "Test")
            self.assertIn("/s/%", request.call_args.args[0])
        with patch.object(client, "request", return_value=(b'<html>Login</html>', 'text/html', '')):
            with self.assertRaises(ValueError):
                client.details("https://z-library.sk/book/abc")

    def test_epub_download_and_reject_html(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = test_epub.EpubTests().make_book(root)
            client = ZLibrary()
            with patch.object(client, "details", return_value=("示例小说", "https://z-library.sk/dl/test")), patch.object(client, "request", return_value=(source.read_bytes(), "application/epub+zip", "")):
                result = client.download("https://z-library.sk/book/abc", root / "downloads")
                self.assertEqual(result.suffix, ".epub")
                self.assertEqual(result.read_bytes(), source.read_bytes())
            with patch.object(client, "details", return_value=("示例", "https://z-library.sk/dl/test")), patch.object(client, "request", return_value=(b"<html>login</html>", "text/html", "")):
                with self.assertRaises(ValueError):
                    client.download("https://z-library.sk/book/abc", root / "downloads")
