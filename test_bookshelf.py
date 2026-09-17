from pathlib import Path
import tempfile
import unittest
from bookshelf import import_book, horizontal_family, horizontal_text


class BookshelfTests(unittest.TestCase):
    def test_copy_deduplicate_and_original_independence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            source = root / "小说.txt"
            source.write_text("第一章\n正文", encoding="utf-8")
            key, stored = import_book(source, root / "library")
            other = root / "改名.txt"
            other.write_bytes(source.read_bytes())
            self.assertEqual(import_book(other, root / "library"), (key, stored))
            source.write_text("另一本书", encoding="utf-8")
            self.assertEqual(stored.read_text(encoding="utf-8"), "第一章\n正文")
            self.assertNotEqual(import_book(source, root / "library")[0], key)
            self.assertEqual(import_book(stored, root / "library"), (key, stored))

    def test_horizontal_font_and_punctuation_preserve_offsets(self):
        self.assertEqual(horizontal_family("@宋体"), "宋体")
        self.assertEqual(horizontal_family("Microsoft YaHei"), "Microsoft YaHei")
        text = "︵你好︶︐﹁测试﹂︒"
        self.assertEqual(horizontal_text(text), "（你好），「测试」。")
        self.assertEqual(len(horizontal_text(text)), len(text))
