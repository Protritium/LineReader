# LineReader · 单行小说阅读器

## [⬇ 下载 Windows 安装包](https://github.com/Protritium/LineReader/releases/latest/download/LineReader-Setup.exe)

[所有版本](https://github.com/Protritium/LineReader/releases) · **简体中文** · [English](README.en.md)

> 首次 Release 成功发布后下载链接才生效。若提示 404，请查看“所有版本”。源码 ZIP 不是安装程序。

该程序由 **“神奇的氕氚”** 开发。欢迎关注 [Protritium 的 GitHub](https://github.com/Protritium)，通过 [GitHub Issues](https://github.com/Protritium/LineReader/issues) 反馈问题和建议。

只显示一行文字的桌面阅读器，支持 TXT、EPUB、透明背景、书架、章节与百分比跳转、每本书独立保存进度。本地阅读无需联网或注册账号。

## 第一次安装（不需要懂代码）

1. 使用 Windows 10 / 11 的 64 位电脑，点击上方“下载 Windows 安装包”。
2. 在浏览器下载列表找到 `LineReader-Setup.exe`，双击打开。
3. 按安装向导点击 Next、Install，安装后打开桌面 LineReader 快捷方式。
4. 不需要安装 Python，也不需要下载源码和构建工具。

安装包暂未使用 Windows 数字证书签名，系统可能显示“未知发布者”。请确认来自本仓库 Releases；程序中的开发者署名不等于 Authenticode 数字签名。

## 开始阅读

1. 在窄条阅读窗口内点击鼠标右键，选择“打开 TXT / EPUB”。
2. 选择电脑上的小说文件。程序会把它复制到数据目录，原文件不会被修改。
3. 按 ↓ 阅读下一行，↑ 返回上一行。没有反应时先左键点击阅读窗口。
4. 换书时右键 →“我的书架”→ 双击书名，即可从上次位置继续。

程序不附带小说。“打开小说网站”按钮使用默认浏览器打开 `https://zlib.bz/`，在浏览器自行完成验证和下载后导入。该网站与本项目无隶属关系；阅读器不自动搜索、登录或下载。

## 常用操作

| 想做什么 | 如何操作 |
| --- | --- |
| 批量添加小说 | 我的书架 → 添加小说 → 选择多个 TXT / EPUB |
| 移动窗口 | 在窗口内部按住左键拖动，包括透明空白处 |
| 改宽度、高度 | 拖动右侧／底部边缘，或右键 → 设置 |
| 改字体、字号、透明度 | 右键 → 设置 → 调整后点击应用 |
| 仅显示文字 | 设置中勾选“仅显示文字”（Windows） |
| 扩大拖动区域 | 设置中增加窗口高度，仍只显示一行文字 |
| 跳转百分比 | 右键 → 跳转进度 → 输入如 `35.5%` |
| 选择章节 | 右键 → 章节列表 → 关键词筛选 → 双击 |
| 隐藏／恢复文字 | Esc，或右键 → 隐藏 / 恢复正文 |
| 作者与反馈 | 右键 → 关于 / 反馈问题 |
| 保存并退出 | 右键 → 退出 |

可选快捷键：Ctrl+O 导入、Ctrl+B 书架、Ctrl+, 设置、Ctrl+G 进度、Ctrl+J 章节、F2 切换透明背景、Ctrl+Q 退出。快捷键需要阅读窗口获得焦点；不熟悉时使用右键菜单即可。

## 数据保存与备份

在资源管理器地址栏粘贴 `%LOCALAPPDATA%\LineReader` 并回车：`library` 保存小说副本，`state.json` 保存书名、设置及独立进度。原文件移动或删除后仍能阅读；相同内容重复导入会去重。覆盖安装和卸载不会主动删除这些个人数据。

备份前先退出程序，再复制整个文件夹。迁移到不同用户名或路径的电脑时，旧进度中的绝对路径可能需要重新关联，暂不保证无缝迁移。

## 常见问题

**字体或标点旋转？** 更新到最新版，选择微软雅黑或宋体。程序过滤 `@` 开头的竖排字体，并转换常见竖排标点的显示形式。缺字字体仍可能由系统回退显示。

**TXT 乱码？** 默认自动检测 UTF-8、GBK / GB18030 等编码。仍异常时，在设置中选择正确编码，点击应用，再重新导入原文件。

**EPUB 打不开？** 支持普通 EPUB 2 / 3 文字及目录，不支持加密正文、PDF 或纯图片扫描书。不显示图片及原书排版。

**章节识别有误？** TXT 采用宽泛正则，可能将短编号列表识别为章节；EPUB 优先读取原书目录。也可使用百分比跳转。

**透明窗口难以操作？** 透明区域仍能点击、拖动和右键。可在设置关闭透明背景，或在窗口有焦点时按 F2。

**拖动异常？** 请在 Issue 中说明 Windows 版本、显示缩放比例、显示器数量和程序版本。实际界面效果需在相应设备上验证。

## 如何反馈问题

打开 [GitHub Issues](https://github.com/Protritium/LineReader/issues)，登录 GitHub，点击 New issue 并选择问题反馈模板。填写版本、复现步骤、预期结果和实际结果，可附截图。请勿上传密码、Cookie、私人阅读数据或完整小说。

## 开发与发布

源码运行需要 Python 3.9+ 和 Tk，安装 `requirements.txt` 后执行 `python reader.py`。测试：`python -m unittest discover -v`。Linux 需要图形桌面；全透明背景主要支持 Windows。

GitHub Actions 在 Windows 上运行测试、PyInstaller 打包、程序启动自检、Inno Setup 制作安装包。推送与 `app_info.py` 及 `installer/LineReader.iss` 一致的标签（如 `v1.7.0`）会发布 Release；手动工作流仅提供构建产物。发布前下载链接不可用。

维护者的 `BUILD-INSTALLER.cmd` 需要另备 `offline-tools` 离线工具包，仓库不包含大型第三方工具。普通用户只需页面顶部的 EXE。
