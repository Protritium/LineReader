# LineReader · Single-line novel reader

## [⬇ Download the Windows installer](https://github.com/Protritium/LineReader/releases/latest/download/LineReader-Setup.exe)

[All releases](https://github.com/Protritium/LineReader/releases) · [简体中文](README.md) · **English**

> The download link works after the first successful Release publication. A 404 means the installer is not yet available. A source ZIP is not an installer.

Developed by **神奇的氕氚 (Protritium)**. Follow [the developer on GitHub](https://github.com/Protritium) and report problems through [GitHub Issues](https://github.com/Protritium/LineReader/issues).

A small desktop reader showing one line at a time. Supports TXT, EPUB, transparent backgrounds, a bookshelf, chapter navigation and saved progress per book. Local reading needs no account or network. The application UI is currently Chinese; this manual provides English instructions.

## Install without coding

1. Use a 64-bit Windows 10 or Windows 11 PC.
2. Click the download link above, then double-click `LineReader-Setup.exe`.
3. Follow the installation wizard and open the desktop shortcut.
4. You do not need Python, source code or build tools.

The installer is not Authenticode-signed. Windows may show “Unknown publisher”; verify the download came from this repository's Releases. Developer attribution is not a digital certificate signature.

## Start reading

Right-click the narrow window → **打开 TXT / EPUB** (Open TXT / EPUB) → select a book. Press Down for the next line and Up for the previous line. Click the window first if keys do not respond.

Open **我的书架** (My bookshelf), then double-click a book to resume. **添加小说** adds multiple books. Imported files are copied to the data directory, duplicate content is deduplicated, and every book retains its own position.

No novels are bundled. **打开小说网站** opens `https://zlib.bz/` in your default browser. Complete any verification and downloads there, then import your file. The website is not affiliated with this project; the reader does not automatically search, log in or download.

## Controls

| Action | Control |
| --- | --- |
| Move | Hold the left button and drag inside the window, including transparent areas |
| Resize | Drag right/bottom edges, or 设置 (Settings) |
| Font, size, opacity | 设置 → adjust → 应用 (Apply) |
| Transparent background | Enable 仅显示文字 (Windows only) |
| Larger drag area | Increase window height in Settings |
| Percentage jump | 跳转进度 → enter e.g. `35.5%` |
| Chapters | 章节列表 → filter → double-click |
| Hide / restore | Esc, or 隐藏 / 恢复正文 |
| Author and support | 关于 / 反馈问题 |
| Save and quit | 退出 |

Optional shortcuts: Ctrl+O import, Ctrl+B bookshelf, Ctrl+, settings, Ctrl+G percentage, Ctrl+J chapters, F2 transparency, Ctrl+Q quit. Shortcuts require focus in the reading window.

## Data and backups

Paste `%LOCALAPPDATA%\LineReader` into File Explorer. `library` contains book copies and `state.json` stores settings and progress. Close the app before backing up the entire folder. Upgrades and uninstalling do not intentionally delete personal data. Moving to a different account or path may require relinking because progress uses absolute file paths.

## Troubleshooting

- Rotated characters: update and select Microsoft YaHei or SimSun. Vertical `@` fonts are filtered; unsupported glyphs can still cause font fallback differences.
- Garbled TXT: select the correct encoding in Settings, apply, then import the original again. Automatic detection covers UTF-8 and common Chinese encodings.
- EPUB errors: supports text-based EPUB 2/3, not DRM-encrypted books, scanned images or PDF. Original layout and illustrations are omitted.
- Inaccurate chapters: TXT uses broad regular expressions; numbered lists can be misidentified. Percentage navigation remains available.
- Dragging issues: report Windows version, scaling, monitor arrangement and app version.

## Feedback

Visit [Issues](https://github.com/Protritium/LineReader/issues), sign in, choose New issue and use the bug template. Include steps, expected/actual behavior and screenshots. Do not upload credentials, cookies, personal reading data or full novels.

## Development

Python 3.9+ with Tk is required. Install `requirements.txt`, run `python reader.py`, and test with `python -m unittest discover -v`. Linux requires a desktop; full transparency targets Windows.

GitHub Actions builds and tests the Windows app and installer. Push a tag matching `app_info.py` and `installer/LineReader.iss` to publish a Release. Manual workflow runs only provide artifacts. The maintainer's `BUILD-INSTALLER.cmd` needs a separate offline tool bundle not included in the repository.
