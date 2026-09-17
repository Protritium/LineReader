import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path
from urllib.parse import quote
from browser_import import DownloadWatch, open_browser
import webbrowser
from zlibrary_source import ZLibrary, site_url, MIRRORS


class ZLibraryDialog:
    def __init__(self, parent, open_book, directory):
        self.window = win = tk.Toplevel(parent)
        win.title("Z-Library 搜索与下载")
        win.geometry("780x640")
        win.attributes("-topmost", True)
        self.client = ZLibrary()
        self.open_book = open_book
        self.directory = directory
        self.queue = queue.Queue()
        self.busy = False
        self.items = []
        self.watcher = None
        self.watch_ticks = 0
        frame = ttk.Frame(win, padding=15)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="选择站点（镜像可用性会变化）").pack(anchor="w")
        self.mirror = tk.StringVar(value="https://zh.zlib.bz")
        ttk.Combobox(frame, textvariable=self.mirror, values=MIRRORS, state="readonly").pack(fill="x", pady=6)
        ttk.Button(frame, text="浏览器打开当前站点", command=lambda: webbrowser.open(self.mirror.get())).pack(anchor="w")
        ttk.Label(frame, text="输入书名搜索，或粘贴所选站点的书籍链接").pack(anchor="w")
        self.query = tk.StringVar()
        ttk.Entry(frame, textvariable=self.query).pack(fill="x", pady=8)
        browser_buttons = ttk.Frame(frame)
        browser_buttons.pack(fill="x", pady=6)
        ttk.Button(browser_buttons, text="小窗口搜索 / 打开链接", command=self.browser_search).pack(side="left")
        ttk.Button(browser_buttons, text="选择下载文件并阅读", command=self.import_file).pack(side="left", padx=8)
        self.watch_label = tk.StringVar(value="自动导入未开启")
        watch_buttons = ttk.Frame(frame)
        watch_buttons.pack(fill="x")
        ttk.Button(watch_buttons, text="选择下载文件夹并监测", command=self.watch_folder).pack(side="left")
        ttk.Button(watch_buttons, text="停止监测", command=self.stop_watch).pack(side="left", padx=8)
        ttk.Label(frame, textvariable=self.watch_label, wraplength=720).pack(anchor="w", pady=6)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="搜索 / 解析链接", command=self.search).pack(side="left")
        ttk.Button(buttons, text="下载所选并阅读", command=self.download).pack(side="left", padx=8)
        ttk.Button(buttons, text="浏览器查看所选", command=self.browse).pack(side="left")
        holder = ttk.Frame(frame)
        holder.pack(fill="both", expand=True, pady=12)
        self.listing = tk.Listbox(holder, exportselection=False)
        scrollbar = ttk.Scrollbar(holder, command=self.listing.yview)
        self.listing.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        self.listing.pack(side="left", fill="both", expand=True)
        self.status = tk.StringVar(value="下载保存到本机；支持 EPUB / TXT。需要网站可从当前电脑访问。")
        ttk.Label(frame, textvariable=self.status, wraplength=660).pack(anchor="w")
        self.job = win.after(100, self.poll)
        win.protocol("WM_DELETE_WINDOW", self.close)

    def browser_search(self):
        value = self.query.get().strip()
        try:
            url = site_url(value) if value.startswith("https://") else self.mirror.get() + ("/s/" + quote(value, safe="") if value else "/")
            self.status.set(open_browser(url))
            self.window.attributes("-topmost", False)
        except (ValueError, OSError) as exc:
            self.status.set(str(exc))

    def import_file(self):
        path = filedialog.askopenfilename(parent=self.window, title="选择已下载的小说", filetypes=[("TXT / EPUB", "*.txt *.epub")])
        if path:
            self.open_book(Path(path))

    def watch_folder(self):
        directory = filedialog.askdirectory(parent=self.window, title="选择浏览器实际保存下载文件的文件夹", initialdir=str(Path.home()))
        if directory:
            try:
                self.watcher = DownloadWatch(directory)
                self.watch_label.set("监测中：" + directory + "（只导入之后新增或更新的 TXT / EPUB）")
            except OSError as exc:
                self.status.set(str(exc))

    def stop_watch(self):
        self.watcher = None
        self.watch_label.set("自动导入已停止")

    def run(self, kind, function):
        if self.busy:
            return
        self.busy = True
        self.status.set("正在搜索…" if kind == "search" else "正在解析并下载…")
        def work():
            try:
                self.queue.put((kind, function(), None))
            except Exception as exc:
                self.queue.put((kind, None, str(exc)))
        threading.Thread(target=work, daemon=True).start()

    def search(self):
        if self.busy:
            return
        self.client = ZLibrary(self.mirror.get())
        value = self.query.get().strip()
        self.items = []
        self.listing.delete(0, "end")
        def work():
            if value.startswith("https://"):
                url = site_url(value)
                title, _ = self.client.details(url)
                return [(title, url)]
            return self.client.search(value)
        self.run("search", work)

    def selected(self):
        selection = self.listing.curselection()
        if not selection:
            messagebox.showinfo("选择书籍", "请先搜索并选择一本书。", parent=self.window)
            return None
        return self.items[selection[0]][1]

    def download(self):
        url = self.selected()
        if url:
            self.run("download", lambda: self.client.download(url, self.directory))

    def browse(self):
        url = self.selected()
        if url:
            webbrowser.open(url)

    def poll(self):
        self.job = self.window.after(100, self.poll)
        self.watch_ticks += 1
        if self.watcher and self.watch_ticks % 10 == 0:
            try:
                ready = self.watcher.poll()
                if ready:
                    latest = max(ready, key=lambda path: path.stat().st_mtime_ns)
                    self.status.set("检测到下载，正在打开：" + latest.name)
                    self.open_book(latest)
            except OSError as exc:
                self.stop_watch()
                self.status.set("监测停止：" + str(exc))
        try:
            kind, result, error = self.queue.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        if error:
            self.status.set("操作失败：" + error)
        elif kind == "search":
            self.items = result
            self.listing.delete(0, "end")
            for title, _ in result:
                self.listing.insert("end", title)
            self.listing.selection_set(0)
            self.status.set(f"找到 {len(result)} 条结果，选择后点击下载。")
        else:
            self.status.set(f"已保存：{result}")
            self.open_book(result)

    def close(self):
        if self.busy:
            messagebox.showinfo("正在处理", "请等待本次请求完成后关闭。", parent=self.window)
            return
        self.window.after_cancel(self.job)
        self.window.destroy()
