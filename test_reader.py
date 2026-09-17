import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, Mock

from reader_core import LineReader, decode_text, normalize_text, find_chapters
from reader_paths import state_path, novel_files
from windows_mouse import RightClickCapture


class LauncherTests(unittest.TestCase):
    def test_smoke_reports_success_and_exception(self):
        import windows_launcher
        import sys
        for failure in (False, True):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory() as directory:
                log = Path(directory) / "中文自检.log"
                app = Mock()
                if failure:
                    app.main.side_effect = RuntimeError("startup failure detail")
                with patch.object(sys, "argv", ["LineReader.exe", "--smoke-test", "--smoke-log", str(log)]), patch.dict(sys.modules, {"reader": app}):
                    code = windows_launcher.main()
                output = log.read_text(encoding="utf-8")
                self.assertEqual(code, int(failure))
                if failure:
                    self.assertIn("startup failure detail", output)
                    self.assertIn("Traceback", output)
                    self.assertNotIn("\nPASS\n", output)
                else:
                    self.assertTrue(output.endswith("PASS\n"))


class DownloadTests(unittest.TestCase):
    def test_text_download_and_html_rejection(self):
        from book_download import download_text
        from email.message import Message
        import io
        def response(data, content_type):
            value = io.BytesIO(data)
            value.url = "https://example.org/book.txt"
            value.headers = Message()
            value.headers["Content-Type"] = content_type
            return value
        text = "第一章 春天\n你好世界。"
        with patch("book_download.urlopen", return_value=response(text.encode("gbk"), "application/octet-stream")):
            self.assertEqual(download_text("https://example.org/book.txt")[0], text)
        with patch("book_download.urlopen", return_value=response(b"<html>Verification</html>", "text/html")):
            with self.assertRaises(ValueError):
                download_text("https://example.org/book.txt")
        with self.assertRaises(ValueError):
            download_text("file:///book.txt")

    def test_download_never_overwrites_existing_book(self):
        from book_download import save_download
        with tempfile.TemporaryDirectory() as directory:
            first = save_download(Path(directory), "小说", "原文")
            second = save_download(Path(directory), "小说", "新版")
            self.assertNotEqual(first, second)
            self.assertEqual(first.read_text(encoding="utf-8"), "原文")
            self.assertEqual(second.read_text(encoding="utf-8"), "新版")
            self.assertEqual(save_download(Path(directory), "CON", "正文").name, "小说_CON.txt")


class RightClickTests(unittest.TestCase):
    def test_hook_drag_updates_tk_geometry_from_fixed_origin(self):
        from reader import ReaderApp
        app = ReaderApp.__new__(ReaderApp)
        app.root = Mock()
        app.root.winfo_x.return_value = 100
        app.root.winfo_y.return_value = 200
        app.root.winfo_width.return_value = 720
        app.root.winfo_height.return_value = 38
        app.canvas = Mock()
        app.canvas.winfo_rootx.return_value = 100
        app.canvas.winfo_rooty.return_value = 200
        app.canvas.winfo_width.return_value = 720
        app.canvas.winfo_height.return_value = 38
        app.captured_drag("start", 150, 210)
        app.captured_drag("move", 200, 240)
        app.root.geometry.assert_called_with("+150+230")
        app.root.winfo_x.return_value = 150
        app.root.winfo_y.return_value = 230
        app.canvas.winfo_rootx.return_value = 150
        app.canvas.winfo_rooty.return_value = 230
        app.captured_drag("end", 250, 260)
        app.root.geometry.assert_called_with("+200+250")

    def test_native_drag_uses_fixed_origin_and_finishes(self):
        import ctypes
        from ctypes import wintypes
        from windows_mouse import NativeDrag
        user = Mock()
        def rectangle(hwnd, pointer):
            rect = ctypes.cast(pointer, ctypes.POINTER(wintypes.RECT)).contents
            rect.left, rect.top, rect.right, rect.bottom = 100, 200, 820, 238
            return True
        user.GetWindowRect.side_effect = rectangle
        mover = NativeDrag(user, 123, Mock())
        mover.handle("start", 150, 210)
        mover.handle("move", 200, 230)
        self.assertEqual(user.SetWindowPos.call_args.args[2:6], (150, 220, 720, 38))
        mover.handle("move", 200, 230)
        self.assertEqual(user.SetWindowPos.call_args.args[2:6], (150, 220, 720, 38))
        mover.handle("end", -10, 180)
        self.assertEqual(user.SetWindowPos.call_args.args[2:6], (-60, 170, 720, 38))
        self.assertIsNone(mover.origin)
        mover.handle("start", 818, 235)
        mover.handle("end", 838, 255)
        self.assertEqual(user.SetWindowPos.call_args.args[2:6], (100, 200, 740, 58))

    def test_capture_click_pair_and_leave_other_buttons_alone(self):
        import ctypes
        from ctypes import wintypes

        class Data(ctypes.Structure):
            _fields_ = [("pt", wintypes.POINT)]

        capture = RightClickCapture.__new__(RightClickCapture)
        capture.mouse_data = Data
        capture.user = Mock()
        capture.user.CallNextHookEx.return_value = 17
        capture.hook = 1
        capture.pressed = False
        capture.pending = None
        capture.on_drag = None
        capture.left_pressed = False
        capture._available = lambda x, y: 100 <= x < 300 and 100 <= y < 140
        point = Data(wintypes.POINT(150, 120))
        address = ctypes.addressof(point)
        self.assertEqual(capture._handle(0, 0x201, address), 17)  # left down
        self.assertEqual(capture._handle(0, 0x204, address), 1)
        self.assertIsNone(capture.pending)
        self.assertEqual(capture._handle(0, 0x205, address), 1)
        self.assertEqual(capture.pending, (150, 120))
        point.pt.x = 400
        self.assertEqual(capture._handle(0, 0x204, address), 17)
        self.assertEqual(capture._handle(0, 0x205, address), 17)
        from collections import deque
        capture.on_drag = Mock()
        capture.drag_events = deque()
        point.pt.x = 150
        self.assertEqual(capture._handle(0, 0x201, address), 1)
        point.pt.x = 450
        self.assertEqual(capture._handle(0, 0x200, address), 17)
        self.assertEqual(capture._handle(0, 0x202, address), 1)
        self.assertEqual(list(capture.drag_events), [("start", 150, 120), ("move", 450, 120), ("end", 450, 120)])
        self.assertFalse(capture.left_pressed)
        self.assertEqual(capture._handle(0, 0x201, address), 17)

    def test_occluding_window_retains_right_click(self):
        capture = RightClickCapture.__new__(RightClickCapture)
        capture.hwnd = 1
        capture.user = Mock()
        capture.user.GetWindow.side_effect = [2, 0]
        capture._contains = lambda hwnd, x, y: True
        self.assertFalse(capture._available(150, 120))
        capture.user.GetWindow.side_effect = [2, 0]
        capture._contains = lambda hwnd, x, y: hwnd == 1
        self.assertTrue(capture._available(150, 120))


class InstallPathTests(unittest.TestCase):
    def test_extracted_bundle_excludes_checksum_manifest(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("SHA256SUMS.txt", "requirements.txt", "README.TXT", "LICENSE.txt", "我的小说.txt", "另一部.TXT"):
                (root / name).write_text("第一章 开始\n正文", encoding="utf-8")
            (root / "目录.txt").mkdir()
            self.assertEqual({p.name for p in novel_files(root)}, {"我的小说.txt", "另一部.TXT"})

    def test_windows_state_is_outside_installation(self):
        actual = state_path("win32", {"LOCALAPPDATA": "/users/me/local"}, "/users/me", "/programs/LineReader/_internal")
        self.assertEqual(actual, Path("/users/me/local/LineReader/state.json"))

    def test_windows_missing_environment(self):
        actual = state_path("win32", {}, "/users/me", "/programs/LineReader")
        self.assertEqual(actual, Path("/users/me/AppData/Local/LineReader/state.json"))

    def test_linux_preserves_source_state(self):
        self.assertEqual(state_path("linux", {}, "/users/me", "/source/read"), Path("/source/read/.reader_state.json"))


class CoreTests(unittest.TestCase):
    def test_chapter_formats_and_offsets(self):
        titles = ["第一章 风起", "第１２回 相遇", "正文 第二卷 归来", "【第三百章】",
                  "Chapter 12: Home", "PART IV The End", "楔子", "番外一 春日",
                  "一、启程", "002 新世界", "（三）归途", "尾聲", "第两百節 重逢"]
        text = normalize_text("\r\n".join("　" + t + "\r\n这里是正文。" for t in titles))
        found = find_chapters(text)
        self.assertEqual([t for t, _ in found], titles)
        for title, offset in found:
            self.assertTrue(text[offset:].startswith(title))

    def test_chapter_duplicates_and_long_body(self):
        text = "第一章 开始\n\n第一章 开始\n正文\n第一章 开始\n" + "第二章 " + "正文" * 100
        self.assertEqual(len(find_chapters(text)), 2)
        self.assertEqual(find_chapters("他读到了第一章。\n普通正文。"), [])

    def test_progress_jump_and_navigation(self):
        book = LineReader("abcdefghij\n\nklmnopqrst\n\n")
        book.next(3, len)
        book.seek_percent("50%", 3, len)
        self.assertEqual(book.history, [])
        self.assertTrue(book.line(3, len))
        book.seek_percent(100, 3, len)
        self.assertEqual(book.line(3, len), "t")
        book.previous(3, len)
        self.assertEqual(book.line(3, len), "qrs")
        book.seek_percent(0, 3, len)
        self.assertEqual(book.line(3, len), "abc")
        for value in ("nan", "inf", -1, 101, "abc"):
            with self.assertRaises(ValueError):
                book.seek_percent(value, 3, len)
        LineReader("").seek_percent(100, 3, len)

    def test_common_encodings(self):
        text = "第一章 春天来了\r\n她说：你好，世界！"
        for encoding in ("utf-8", "utf-8-sig", "gbk", "gb18030", "utf-16", "utf-32"):
            with self.subTest(encoding=encoding):
                self.assertEqual(decode_text(text.encode(encoding))[0], text)

    def test_big5_override(self):
        text = "第一章 春天來了，她說你好！"
        self.assertEqual(decode_text(text.encode("big5"), "big5")[0], text)

    def test_bomless_utf16(self):
        for codec in ("utf-16-le", "utf-16-be"):
            self.assertEqual(decode_text("Chapter 1 你好".encode(codec))[0], "Chapter 1 你好")

    def test_invalid_does_not_silently_replace(self):
        with self.assertRaises(ValueError):
            decode_text(b"\x81")

    def test_forward_back_no_lost_characters(self):
        text = "第一章\r\n\r\n　　你好，这是一个很长的段落。Hello world!\n最后一行"
        book = LineReader(text)
        starts, lines = [], []
        measure = lambda s: sum(2 if ord(c) > 127 else 1 for c in s)
        while True:
            starts.append(book.offset)
            lines.append(book.line(11, measure))
            book.next(11, measure)
            if book.offset == starts[-1]:
                break
        self.assertEqual("".join(lines), normalize_text(text).replace("\n", ""))
        for expected in reversed(starts[:-1]):
            book.previous(11, measure)
            self.assertEqual(book.offset, expected)

    def test_resume_previous_and_resize(self):
        book = LineReader("abcdefghij\n\nklmnopqrst", 15)
        self.assertEqual(book.line(3, len), "nop")
        book.previous(3, len)
        self.assertEqual(book.line(3, len), "klm")
        book.previous(3, len)
        self.assertEqual(book.line(3, len), "j")
        book.reflow()
        offset = book.offset
        book.next(5, len)
        book.previous(5, len)
        self.assertEqual(book.offset, offset)

    def test_narrow_empty_and_long_paragraph(self):
        self.assertEqual(LineReader("你好").line(1, lambda s: len(s) * 20), "你")
        empty = LineReader("")
        empty.next(10, len)
        empty.previous(10, len)
        self.assertEqual(empty.line(10, len), "")
        self.assertEqual(LineReader("a" * 1000000).line(80, len), "a" * 80)


class DesktopTests(unittest.TestCase):
    def test_navigation_settings_and_persistence(self):
        import tkinter as tk
        import reader
        try:
            root = tk.Tk()
        except tk.TclError:
            self.skipTest("需要图形显示服务")
        try:
            with tempfile.TemporaryDirectory() as directory:
                novel = Path(directory) / "sample.txt"
                novel.write_bytes(("第一章 开始\n" + "你好世界。" * 100 + "\n第二章 结束\n" + "下一章。" * 100).encode("gbk"))
                state = Path(directory) / "state.json"
                with patch.object(reader, "STATE", state):
                    app = reader.ReaderApp(root, novel)
                    root.update()
                    app.move(1)
                    self.assertGreater(app.book.offset, 0)
                    offset = app.book.offset
                    app.toggle_blank()
                    self.assertEqual(app.canvas.itemcget(app.item, "text"), "")
                    app.toggle_blank()
                    app.settings()
                    root.update()
                    self.assertTrue(app.dialog.winfo_exists())
                    app.show_chapters()
                    root.update()
                    self.assertTrue(app.chapter_dialog.winfo_exists())
                    if root.tk.call("tk", "windowingsystem") == "win32":
                        self.assertEqual(str(root.attributes("-transparentcolor")), "#ffffff")
                        app.toggle_transparent()
                        self.assertEqual(str(root.attributes("-transparentcolor")), "")
                        app.toggle_transparent()
                    with patch.object(reader.simpledialog, "askstring", return_value="50%"):
                        app.jump_progress()
                    self.assertGreater(app.book.offset, offset)
                    offset = app.book.offset
                    app.save()
                    import json
                    self.assertEqual(json.loads(state.read_text(encoding="utf-8"))["positions"][str(app.path)], offset)
                    stored_path = app.path
                    self.assertNotEqual(stored_path, novel)
                    self.assertTrue(stored_path.is_file())
                    app.load_file(novel)
                    self.assertEqual(app.path, stored_path)
                    self.assertEqual(app.book.offset, offset)
                    self.assertEqual(len(app.state["library"]), 1)
                    app.show_bookshelf()
                    root.update()
        finally:
            root.destroy()


if __name__ == "__main__":
    unittest.main()
