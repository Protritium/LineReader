#!/usr/bin/env python3
"""A borderless, single-line desktop TXT reader. Python 3.9+."""
import argparse
import json
import os
import webbrowser
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, font, messagebox, simpledialog, ttk

from reader_core import LineReader, decode_text
from reader_paths import BASE, BOOKS, STATE, novel_files
from windows_mouse import RightClickCapture, enable_windows_dpi
from types import SimpleNamespace
from epub_reader import read_epub
from bookshelf import import_book, horizontal_family, horizontal_text
from app_info import VERSION, AUTHOR, PROFILE, REPOSITORY, ISSUES

DEFAULTS = dict(width=720, height=38, alpha=0.94, size=16,
                family="", theme="记事本", topmost=True, encoding="auto", transparent=True)
THEMES = {"记事本": ("#ffffff", "#202020"), "Word 纸张": ("#faf9f6", "#303030"),
          "浅灰": ("#f0f0f0", "#333333")}


class ReaderApp:
    def __init__(self, root, initial=None, restore_state=True):
        self.root = root
        self.state = {}
        try:
            source = STATE if STATE.exists() else BASE / ".reader_state.json"
            value = json.loads(source.read_text(encoding="utf-8")) if restore_state else {}
            if isinstance(value, dict):
                self.state = value
        except (OSError, ValueError):
            pass
        self.options = {**DEFAULTS, **self.state.get("options", {})}
        self.options["family"] = horizontal_family(self.options["family"])
        self.book = LineReader("")
        self.path = None
        self.encoding = ""
        self.hidden = False
        self.dialog = None
        self.chapter_dialog = None
        self.save_job = None
        self.last_size = None
        root.title("文本")
        root.overrideredirect(True)
        root.minsize(160, 24)
        self.canvas = tk.Canvas(root, highlightthickness=0, borderwidth=0)
        self.canvas.pack(fill="both", expand=True)
        self.item = self.canvas.create_text(12, 19, anchor="w", text="")
        self.text_font = font.Font(root, size=self.options["size"])
        if not self.options["family"]:
            families = set(font.families(root))
            self.options["family"] = next((f for f in ("Microsoft YaHei", "Noto Sans CJK SC", "WenQuanYi Micro Hei", "SimSun") if f in families), "TkDefaultFont")
        root.geometry(f'{self.options["width"]}x{self.options["height"]}')
        root.bind("<Configure>", self.on_resize)
        root.bind("<Up>", lambda e: self.move(-1))
        root.bind("<Down>", lambda e: self.move(1))
        root.bind("<Escape>", self.toggle_blank)
        root.bind("<Control-o>", lambda e: self.open_file())
        root.bind("<Control-comma>", lambda e: self.settings())
        root.bind("<Control-g>", lambda e: self.jump_progress())
        root.bind("<Control-j>", lambda e: self.show_chapters())
        root.bind("<Control-b>", lambda e: self.show_bookshelf())
        root.bind("<F2>", lambda e: self.toggle_transparent())
        root.bind("<Control-q>", lambda e: self.close())
        root.bind("<Alt-F4>", lambda e: self.close())
        self.canvas.bind("<ButtonPress-1>", self.drag_start)
        self.canvas.bind("<B1-Motion>", self.drag)
        self.canvas.bind("<Motion>", self.cursor)
        self.canvas.bind("<Button-3>", self.menu)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.apply_options()
        candidate = initial or self.state.get("last_file")
        if not initial and candidate and Path(candidate).name.casefold() == "sha256sums.txt":
            candidate = None
        if not candidate or not Path(candidate).is_file():
            candidate = next(iter(novel_files(BOOKS)), None)
        if candidate:
            self.load_file(candidate)
        else:
            self.render()
        try:
            self.mouse_capture = RightClickCapture(root, self.popup_menu, self.captured_drag)
            if self.mouse_capture.hook:
                # Only the hook feeds drag events; Tk owns window geometry.
                self.canvas.unbind("<ButtonPress-1>")
                self.canvas.unbind("<B1-Motion>")
        except OSError as exc:
            self.options["transparent"] = False
            self.apply_options()
            messagebox.showwarning("已切换实色背景", f"无法启用透明区域右键操作，已恢复实色背景以便使用鼠标。\n{exc}", parent=root)
        root.after(100, root.focus_force)

    def width(self):
        return max(1, self.canvas.winfo_width() - 24)

    def measure(self, text):
        return self.text_font.measure(horizontal_text(text))

    def render(self):
        text = "" if self.hidden else self.book.line(self.width(), self.measure)
        if not self.path and not self.hidden:
            text = "右键打开 TXT / EPUB · ↑↓ 翻行"
        self.canvas.itemconfigure(self.item, text=horizontal_text(text))
        self.canvas.coords(self.item, 12, self.canvas.winfo_height() / 2)

    def move(self, direction):
        if self.hidden:
            return
        action = self.book.next if direction > 0 else self.book.previous
        action(self.width(), self.measure)
        self.render()
        self.schedule_save()

    def toggle_blank(self, event=None):
        self.hidden = not self.hidden
        self.render()

    def on_resize(self, event):
        if event.widget is self.root:
            size = (event.width, event.height)
            if size != self.last_size:
                self.last_size = size
                self.book.reflow()
                self.root.after_idle(self.render)
                self.schedule_save()

    def cursor(self, event):
        edge = event.x >= self.canvas.winfo_width() - 8 or event.y >= self.canvas.winfo_height() - 6
        self.canvas.configure(cursor="size_nw_se" if edge and os.name == "nt" else "bottom_right_corner" if edge else "arrow")

    def drag_start(self, event):
        self.root.focus_force()
        self.drag_origin = (event.x_root, event.y_root, self.root.winfo_x(), self.root.winfo_y(), self.root.winfo_width(), self.root.winfo_height())
        self.resizing = event.x >= self.canvas.winfo_width() - 8 or event.y >= self.canvas.winfo_height() - 6

    def captured_drag(self, kind, x, y):
        event = SimpleNamespace(x_root=x, y_root=y,
                                x=x - self.canvas.winfo_rootx(), y=y - self.canvas.winfo_rooty())
        if kind == "start":
            self.drag_start(event)
        else:
            self.drag(event)

    def drag(self, event):
        x, y, rx, ry, w, h = self.drag_origin
        dx, dy = event.x_root - x, event.y_root - y
        if self.resizing:
            self.root.geometry(f"{max(160, w + dx)}x{max(24, h + dy)}")
        else:
            self.root.geometry(f"+{max(0, rx + dx)}+{max(0, ry + dy)}")

    def menu(self, event):
        self.popup_menu(event.x_root, event.y_root)

    def popup_menu(self, x, y):
        self.root.focus_force()
        menu = tk.Menu(self.root, tearoff=False)
        menu.add_command(label="打开 TXT / EPUB…    Ctrl+O", command=self.open_file)
        menu.add_command(label="我的书架…    Ctrl+B", command=self.show_bookshelf)
        menu.add_command(label="打开小说网站", command=self.open_book_website)
        menu.add_command(label="设置…    Ctrl+,", command=self.settings)
        menu.add_command(label="跳转进度…    Ctrl+G", command=self.jump_progress)
        menu.add_command(label="章节列表…    Ctrl+J", command=self.show_chapters)
        menu.add_command(label="透明背景 / 实色背景    F2", command=self.toggle_transparent)
        menu.add_command(label="隐藏 / 恢复正文    Esc", command=self.toggle_blank)
        menu.add_separator()
        menu.add_command(label="关于 / 反馈问题", command=self.about)
        menu.add_command(label="退出    Ctrl+Q", command=self.close)
        try:
            menu.tk_popup(x, y)
        finally:
            menu.grab_release()

    def open_file(self):
        initial_dir = self.path.parent if self.path else BOOKS
        path = filedialog.askopenfilename(parent=self.dialog or self.root, title="打开小说", initialdir=str(initial_dir), filetypes=[("小说文件", "*.txt *.epub"), ("EPUB 电子书", "*.epub"), ("TXT 文本", "*.txt"), ("所有文件", "*")])
        if path:
            self.load_file(path)

    def open_book_website(self):
        try:
            if not webbrowser.open("https://zlib.bz/"):
                raise OSError("无法启动默认浏览器，请检查系统浏览器设置。")
        except OSError as exc:
            messagebox.showerror("无法打开网站", str(exc), parent=self.dialog or self.root)

    def about(self):
        win = tk.Toplevel(self.root)
        win.title("关于 LineReader")
        win.attributes("-topmost", True)
        frame = ttk.Frame(win, padding=24)
        frame.pack()
        ttk.Label(frame, text=f"LineReader {VERSION}\n\n该程序由“{AUTHOR}”开发。\n欢迎关注 GitHub，并通过 GitHub Issues 反馈问题。", justify="left").pack(anchor="w")
        for label, url in (("开发者 GitHub", PROFILE), ("项目仓库 / 下载更新", REPOSITORY), ("反馈问题（GitHub Issues）", ISSUES)):
            ttk.Button(frame, text=label, command=lambda target=url: webbrowser.open(target)).pack(fill="x", pady=5)

    def load_file(self, path, encoding_override=None):
        try:
            path = Path(path).resolve()
            saved_entry = self.state.get("library", {}).get(path.name, {})
            stored_encoding = saved_entry.get("encoding") if saved_entry.get("path") == str(path) else None
            chapters = None
            if path.suffix.casefold() == ".epub":
                text, chapters = read_epub(path)
                encoding = "EPUB"
            else:
                text, encoding = decode_text(path.read_bytes(), encoding_override or stored_encoding or self.options["encoding"])
            if not text.strip():
                raise ValueError("此文件没有可阅读的正文。")
            self.save()
            source = path
            key, path = import_book(source, STATE.parent / "library")
            shelf = self.state.setdefault("library", {})
            existing = shelf.get(key, {})
            offset = self.state.get("positions", {}).get(str(path), self.state.get("positions", {}).get(str(source), 0))
            book = LineReader(text, offset)
            if chapters:
                book.chapters = chapters
            shelf[key] = {"title": existing.get("title", source.stem), "path": str(path),
                          "length": len(book.text), "encoding": encoding}
        except (OSError, UnicodeError, ValueError) as exc:
            messagebox.showerror("无法打开文本", str(exc), parent=self.dialog or self.root)
            return
        self.path, self.book, self.encoding = path, book, encoding
        if self.chapter_dialog:
            self.chapter_dialog.destroy()
            self.chapter_dialog = None
        self.hidden = False
        self.render()
        self.schedule_save()
        self.save()
        if self.dialog:
            self.info.set(self.file_info())

    def apply_options(self):
        self.options["family"] = horizontal_family(self.options["family"])
        self.text_font.configure(family=self.options["family"], size=int(self.options["size"]))
        bg, fg = THEMES[self.options["theme"]]
        if self.root.tk.call("tk", "windowingsystem") == "win32":
            if self.options["transparent"]:
                bg = "#ffffff"
            self.root.attributes("-transparentcolor", bg if self.options["transparent"] else "")
        self.canvas.configure(background=bg)
        self.canvas.itemconfigure(self.item, font=self.text_font, fill=fg)
        self.root.attributes("-topmost", bool(self.options["topmost"]))
        try:
            self.root.attributes("-alpha", float(self.options["alpha"]))
        except tk.TclError:
            pass
        self.book.reflow()
        self.render()

    def toggle_transparent(self):
        if self.root.tk.call("tk", "windowingsystem") != "win32":
            messagebox.showinfo("透明背景", "仅显示文字模式目前支持 Windows；此系统可使用不透明度设置。", parent=self.root)
            return
        self.options["transparent"] = not self.options["transparent"]
        self.apply_options()
        self.schedule_save()

    def after_jump(self):
        self.hidden = False
        self.render()
        self.schedule_save()
        if self.dialog:
            self.info.set(self.file_info())
        self.root.focus_force()

    def jump_progress(self):
        if not self.path:
            return
        value = simpledialog.askstring("跳转进度", "输入百分比（0–100，可用小数）：", parent=self.dialog or self.root,
                                       initialvalue=f"{self.book.offset / max(1, len(self.book.text)) * 100:.2f}")
        if value is None:
            return
        try:
            self.book.seek_percent(value, self.width(), self.measure)
        except ValueError:
            messagebox.showerror("进度无效", "请输入 0–100 之间的数字，例如 35.5 或 35.5%。", parent=self.dialog or self.root)
            return
        self.after_jump()

    def show_chapters(self):
        if self.chapter_dialog and self.chapter_dialog.winfo_exists():
            self.chapter_dialog.lift()
            return
        dlg = self.chapter_dialog = tk.Toplevel(self.root)
        dlg.title(f"章节列表 · {len(self.book.chapters)} 章")
        dlg.geometry("560x480")
        dlg.attributes("-topmost", True)
        frame = ttk.Frame(dlg, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="输入关键词筛选；双击章节或按 Enter 跳转").pack(anchor="w")
        query = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=query)
        entry.pack(fill="x", pady=8)
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True)
        listing = tk.Listbox(holder, exportselection=False)
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=listing.yview)
        listing.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        listing.pack(side="left", fill="both", expand=True)
        visible = []

        def populate(*args):
            visible[:] = [(title, offset) for title, offset in self.book.chapters if query.get().casefold() in title.casefold()]
            listing.delete(0, "end")
            current = 0
            for index, (title, offset) in enumerate(visible):
                listing.insert("end", title)
                if offset <= self.book.offset:
                    current = index
            if visible:
                listing.selection_set(current)
                listing.see(current)

        def dismiss():
            dlg.destroy()
            self.chapter_dialog = None
            self.root.focus_force()

        def choose(event=None):
            selected = listing.curselection()
            if selected:
                self.book.seek(visible[selected[0]][1])
                dismiss()
                self.after_jump()

        query.trace_add("write", populate)
        listing.bind("<Double-Button-1>", choose)
        listing.bind("<Return>", choose)
        ttk.Button(frame, text="跳转所选章节", command=choose).pack(pady=(8, 0))
        if not self.book.chapters:
            ttk.Label(frame, text="未识别到章节标题，可以使用 Ctrl+G 按百分比跳转。").pack()
        dlg.protocol("WM_DELETE_WINDOW", dismiss)
        populate()
        entry.focus_set()

    def file_info(self):
        progress = self.book.offset / max(1, len(self.book.text)) * 100
        title = self.state.get("library", {}).get(self.path.name, {}).get("title", self.path.stem) if self.path else "尚未打开文件"
        return f"{title}\n编码：{self.encoding or '—'}    阅读位置：{progress:.1f}%"

    def settings(self):
        if self.dialog and self.dialog.winfo_exists():
            self.dialog.lift()
            return
        dlg = self.dialog = tk.Toplevel(self.root)
        dlg.title("文本设置")
        dlg.resizable(False, False)
        dlg.attributes("-topmost", True)
        frame = ttk.Frame(dlg, padding=18)
        frame.pack(fill="both", expand=True)
        self.info = tk.StringVar(value=self.file_info())
        ttk.Label(frame, textvariable=self.info, wraplength=420).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 12))
        variables = {}
        fields = [("width", "窗口宽度", self.root.winfo_width()), ("height", "窗口高度", self.root.winfo_height()),
                  ("size", "字号", self.options["size"]), ("family", "字体", self.options["family"]),
                  ("theme", "背景风格", self.options["theme"]), ("encoding", "打开文件使用的编码", self.options["encoding"])]
        for row, (key, label, value) in enumerate(fields, 1):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 18), pady=5)
            var = variables[key] = tk.StringVar(value=str(value))
            if key in ("theme", "encoding", "family"):
                values = list(THEMES) if key == "theme" else ["auto", "utf-8-sig", "gb18030", "gbk", "big5", "utf-16", "utf-16-le", "utf-16-be"] if key == "encoding" else sorted(f for f in font.families() if not f.startswith("@"))
                entry = ttk.Combobox(frame, textvariable=var, values=values, state="readonly", width=25)
            else:
                entry = ttk.Entry(frame, textvariable=var, width=28)
            entry.grid(row=row, column=1, sticky="ew")
        ttk.Label(frame, text="不透明度（20%–100%）").grid(row=7, column=0, sticky="w", pady=8)
        alpha = tk.DoubleVar(value=self.options["alpha"])
        ttk.Scale(frame, from_=0.2, to=1.0, variable=alpha, command=lambda v: self.root.attributes("-alpha", float(v))).grid(row=7, column=1, sticky="ew")
        topmost = tk.BooleanVar(value=self.options["topmost"])
        ttk.Checkbutton(frame, text="窗口置顶", variable=topmost).grid(row=8, column=0, sticky="w")
        transparent = tk.BooleanVar(value=self.options["transparent"])
        ttk.Checkbutton(frame, text="仅显示文字（Windows 透明背景）", variable=transparent,
                        state="normal" if self.root.tk.call("tk", "windowingsystem") == "win32" else "disabled").grid(row=8, column=1, sticky="w")
        ttk.Label(frame, text="↑ / ↓ 上一行 / 下一行；Esc 清空或恢复正文\n拖动正文移动窗口，拖动右侧或底部边缘调整大小。\n编码选择后点击应用，再重新打开文件。", foreground="#666666").grid(row=9, column=0, columnspan=2, pady=12, sticky="w")

        def apply():
            try:
                updated = {k: v.get() for k, v in variables.items()}
                for key, low, high in (("width", 160, 10000), ("height", 24, 2000), ("size", 8, 72)):
                    updated[key] = int(updated[key])
                    if not low <= updated[key] <= high:
                        raise ValueError(f"{key} 必须在 {low}–{high} 之间")
                updated.update(alpha=alpha.get(), topmost=topmost.get(), transparent=transparent.get())
                self.options.update(updated)
                self.root.geometry(f'{updated["width"]}x{updated["height"]}')
                self.apply_options()
                self.schedule_save()
            except (ValueError, tk.TclError) as exc:
                messagebox.showerror("设置无效", str(exc), parent=dlg)

        def dismiss():
            self.root.attributes("-alpha", self.options["alpha"])
            dlg.destroy()
            self.dialog = None
            self.root.focus_force()

        buttons = ttk.Frame(frame)
        buttons.grid(row=10, column=0, columnspan=2, sticky="e")
        ttk.Button(buttons, text="打开 TXT / EPUB", command=self.open_file).pack(side="left", padx=4)
        ttk.Button(buttons, text="打开小说网站", command=self.open_book_website).pack(side="left", padx=4)
        ttk.Button(buttons, text="应用", command=apply).pack(side="left", padx=4)
        ttk.Button(buttons, text="返回阅读", command=dismiss).pack(side="left", padx=4)
        dlg.protocol("WM_DELETE_WINDOW", dismiss)
        navigation = ttk.Frame(frame)
        navigation.grid(row=11, column=0, columnspan=2, sticky="e", pady=(8, 0))
        ttk.Button(navigation, text="跳转进度", command=self.jump_progress).pack(side="left", padx=4)
        ttk.Button(navigation, text="章节列表", command=self.show_chapters).pack(side="left", padx=4)
        ttk.Button(navigation, text="我的书架", command=self.show_bookshelf).pack(side="left", padx=4)
        ttk.Button(navigation, text="关于 / 反馈", command=self.about).pack(side="left", padx=4)

    def show_bookshelf(self):
        self.save()
        win = tk.Toplevel(self.root)
        win.title("我的书架")
        win.geometry("640x440")
        win.attributes("-topmost", True)
        frame = ttk.Frame(win, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="双击继续阅读；导入后原文件移动或删除不影响书架。", wraplength=600).pack(anchor="w")
        tree = ttk.Treeview(frame, columns=("title", "progress"), show="headings", selectmode="browse")
        tree.heading("title", text="小说")
        tree.heading("progress", text="进度")
        tree.column("title", width=460)
        tree.column("progress", width=80)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        tree.pack(fill="both", expand=True, pady=8)

        def refresh():
            tree.delete(*tree.get_children())
            for key, item in self.state.get("library", {}).items():
                offset = self.state.get("positions", {}).get(item["path"], 0)
                progress = offset / max(1, item.get("length", 0)) * 100
                tree.insert("", "end", iid=key, values=(item["title"], f"{progress:.1f}%"))

        def choose(event=None):
            selected = tree.selection()
            if selected:
                item = self.state["library"][selected[0]]
                codec = item.get("encoding")
                self.load_file(item["path"], codec if codec != "EPUB" else None)
                win.destroy()
                self.root.focus_force()

        def add():
            paths = filedialog.askopenfilenames(parent=win, title="添加小说", filetypes=[("TXT / EPUB", "*.txt *.epub")])
            for path in paths:
                self.load_file(path)
            refresh()

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="添加小说", command=add).pack(side="left")
        ttk.Button(buttons, text="继续阅读", command=choose).pack(side="right")
        tree.bind("<Double-Button-1>", choose)
        tree.bind("<Return>", choose)
        refresh()

    def schedule_save(self):
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.save_job = self.root.after(400, self.save)

    def save(self):
        if self.save_job:
            self.root.after_cancel(self.save_job)
        self.save_job = None
        if self.path:
            self.state.setdefault("positions", {})[str(self.path)] = self.book.offset
            self.state["last_file"] = str(self.path)
        self.options["width"] = max(160, self.root.winfo_width())
        self.options["height"] = max(24, self.root.winfo_height())
        self.state["options"] = self.options
        try:
            STATE.parent.mkdir(parents=True, exist_ok=True)
            temp = STATE.with_suffix(".tmp")
            temp.write_text(json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(STATE)
        except OSError as exc:
            print(f"无法保存阅读进度：{exc}")

    def close(self):
        self.save()
        self.root.destroy()


def main():
    enable_windows_dpi()
    parser = argparse.ArgumentParser(description="单行 TXT / EPUB 桌面阅读器")
    parser.add_argument("file", nargs="?", help="可选的小说 TXT / EPUB 路径")
    parser.add_argument("--smoke-test", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--smoke-log", help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        parser.exit(1, f"无法启动桌面窗口：{exc}\n请在有图形桌面的电脑上运行；纯 SSH 会话无法显示窗口。\n")
    if args.smoke_test:
        smoke_test(root, args.smoke_log)
        return
    ReaderApp(root, args.file)
    root.mainloop()


def smoke_test(root, log_path=None):
    """Exercise the frozen executable without touching real reading progress."""
    global STATE
    import tempfile
    import chardet
    def checkpoint(message):
        if log_path:
            with Path(log_path).open("a", encoding="utf-8") as stream:
                stream.write(message + "\n")

    original_state = STATE
    try:
        with tempfile.TemporaryDirectory(prefix="linereader-check-") as directory:
            STATE = Path(directory) / "state.json"
            checkpoint(f"Tk initialized; books directory: {BOOKS}")
            fixture = Path(directory) / "smoke.txt"
            fixture.write_text("第一章 测试\n" + "测试正文。" * 200 + "\n第二章 结束\n" + "结束正文。" * 100, encoding="utf-8")
            app = ReaderApp(root, fixture, restore_state=False)
            root.update()
            checkpoint(f"Reader initialized; loaded: {app.path}; encoding: {app.encoding}")
            if not app.path or not app.book.text:
                raise RuntimeError("Bundled novel was not loaded")
            first = app.book.offset
            app.move(1)
            if app.book.offset <= first:
                raise RuntimeError("Navigation failed")
            app.move(-1)
            if app.book.offset != first:
                raise RuntimeError("Reverse navigation failed")
            checkpoint("Forward/reverse navigation passed")
            app.toggle_blank()
            if app.canvas.itemcget(app.item, "text"):
                raise RuntimeError("Blanking failed")
            app.toggle_blank()
            app.settings()
            root.update()
            checkpoint("Settings window opened")
            app.show_chapters()
            root.update()
            checkpoint(f"Chapter window opened; chapters: {len(app.book.chapters)}")
            if not app.book.chapters:
                raise RuntimeError("Bundled novel chapter detection failed")
            app.book.seek(app.book.chapters[-1][1])
            if not app.book.line(app.width(), app.text_font.measure):
                raise RuntimeError("Chapter navigation failed")
            app.book.seek_percent(50, app.width(), app.text_font.measure)
            if app.book.offset <= first:
                raise RuntimeError("Percentage navigation failed")
            checkpoint("Chapter/percentage navigation passed")
            if root.tk.call("tk", "windowingsystem") == "win32":
                if not str(root.attributes("-transparentcolor")):
                    raise RuntimeError("Transparent background was not enabled")
            app.book.seek(first)
            app.save()
            saved = json.loads(STATE.read_text(encoding="utf-8"))
            if saved["positions"][str(app.path)] != first:
                raise RuntimeError("Progress persistence failed")
            checkpoint("Transparency and persistence passed")
            root.destroy()
            checkpoint("Window cleanup passed")
    finally:
        STATE = original_state
        try:
            root.destroy()
        except tk.TclError:
            pass


if __name__ == "__main__":
    main()
