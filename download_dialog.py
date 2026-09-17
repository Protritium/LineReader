import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox
from urllib.parse import urlencode
import webbrowser

from book_download import download_text, save_download


class DownloadDialog:
    def __init__(self, parent, open_book, directory):
        self.window = window = tk.Toplevel(parent)
        window.title("搜索 / 下载小说")
        window.attributes("-topmost", True)
        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        self.title = tk.StringVar()
        self.url = tk.StringVar()
        self.status = tk.StringVar(value="搜索在浏览器中打开；下载需要实际 TXT 链接。")
        self.results = queue.Queue()
        self.open_book = open_book
        self.directory = directory
        self.busy = False
        self.closed = False
        ttk.Label(frame, text="小说名称 / 搜索关键词").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.title, width=64).pack(fill="x", pady=6)
        buttons = ttk.Frame(frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="搜索该网站", command=self.search).pack(side="left", padx=(0, 8))
        ttk.Button(buttons, text="打开 c6k6 网站", command=lambda: webbrowser.open("https://m.c6k6.com/")).pack(side="left")
        ttk.Label(frame, text="TXT 下载链接（在网页下载按钮上右键复制链接）").pack(anchor="w", pady=(16, 0))
        ttk.Entry(frame, textvariable=self.url, width=64).pack(fill="x", pady=6)
        self.button = ttk.Button(frame, text="下载并阅读", command=self.download)
        self.button.pack(anchor="e")
        ttk.Label(frame, textvariable=self.status, wraplength=480).pack(anchor="w", pady=(12, 0))
        ttk.Label(frame, text=f"保存目录：{directory}", wraplength=480).pack(anchor="w", pady=(6, 0))
        window.protocol("WM_DELETE_WINDOW", self.close)
        self.job = window.after(100, self.poll)

    def search(self):
        keyword = self.title.get().strip()
        if not keyword:
            messagebox.showinfo("输入书名", "请先输入小说名称。", parent=self.window)
            return
        webbrowser.open("https://www.bing.com/search?" + urlencode({"q": "site:c6k6.com " + keyword}))

    def download(self):
        if self.busy:
            return
        url, title = self.url.get().strip(), self.title.get().strip()
        if not url or not title:
            messagebox.showinfo("填写信息", "请填写小说名称和 TXT 下载链接。", parent=self.window)
            return
        self.busy = True
        self.button.configure(state="disabled")
        self.status.set("正在下载，请稍候……")

        def worker():
            try:
                text, encoding = download_text(url)
                path = save_download(self.directory, title, text)
                self.results.put((path, encoding, None))
            except Exception as exc:
                self.results.put((None, None, str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        if self.closed:
            return
        self.job = self.window.after(100, self.poll)
        try:
            path, encoding, error = self.results.get_nowait()
        except queue.Empty:
            return
        self.busy = False
        self.button.configure(state="normal")
        if error:
            self.status.set("下载失败：" + error)
        else:
            self.status.set(f"已保存：{path.name}（原编码 {encoding}，保存为 UTF-8）")
            self.open_book(path)

    def close(self):
        if self.busy:
            messagebox.showinfo("正在下载", "请等待本次下载完成后关闭窗口。", parent=self.window)
            return
        self.closed = True
        self.window.after_cancel(self.job)
        self.window.destroy()
