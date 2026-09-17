from pathlib import Path
import tempfile
import unittest
from browser_import import DownloadWatch


class WatchTests(unittest.TestCase):
    def test_only_completed_new_downloads(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "old.txt").write_text("原书", encoding="utf-8")
            now = [0]
            watch = DownloadWatch(root, lambda: now[0])
            self.assertEqual(watch.poll(), [])
            book = root / "new.txt"
            book.write_text("新书", encoding="utf-8")
            self.assertEqual(watch.poll(), [])
            now[0] = 2
            book.write_text("新书已完成", encoding="utf-8")
            self.assertEqual(watch.poll(), [])
            now[0] = 4
            self.assertEqual(watch.poll(), [])
            now[0] = 6
            self.assertEqual(watch.poll(), [book])
            self.assertEqual(watch.poll(), [])

    def test_partial_download_is_ignored(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            now = [0]
            watch = DownloadWatch(root, lambda: now[0])
            (root / "book.epub.crdownload").write_bytes(b"partial")
            self.assertEqual(watch.poll(), [])
            now[0] = 10
            self.assertEqual(watch.poll(), [])
