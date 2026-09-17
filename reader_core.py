"""Text decoding and pixel-width navigation, independent of the GUI."""
import codecs
import math
import re


NUMBER = r"[0-9０-９零〇一二三四五六七八九十百千万萬两兩壹贰貳叁參肆伍陆陸柒捌玖拾佰仟]+"
CHAPTER_PATTERN = re.compile(
    rf"^(?:(?:正文|作品正文)\s*[:：]?\s*)?(?:"
    rf"第\s*{NUMBER}\s*[章回节節卷部篇集](?:.*)|"
    rf"(?:chapter|chap\.?|part|book|volume)\s+(?:\d+|[ivxlcdm]+)\b.*|"
    rf"(?:序章|序言|前言|楔子|引子|引言|尾声|尾聲|终章|終章|后记|後記|结语|結語|大结局|大結局|番外|外传|外傳)(?:.*)|"
    rf"{NUMBER}(?:[、.．:：）)]\s*|\s+)\S.*|"
    rf"[（(]\s*{NUMBER}\s*[）)](?:.*)|"
    rf"{NUMBER})$", re.IGNORECASE)


def find_chapters(text):
    """Return (title, offset) in normalized text; constrain matches to short lines."""
    chapters = []
    for match in re.finditer(r"[^\n]+", text):
        title = match.group().strip()
        if not title or len(title) > 100:
            continue
        candidate = title.strip("【】[]《》*# —-=\t")
        if CHAPTER_PATTERN.fullmatch(candidate):
            offset = match.start() + len(match.group()) - len(match.group().lstrip())
            if chapters and title == chapters[-1][0]:
                previous_title, previous_offset = chapters[-1]
                if not text[previous_offset + len(previous_title):offset].strip():
                    continue
            chapters.append((title, offset))
    return chapters


def decode_text(data, encoding="auto"):
    if encoding != "auto":
        return data.decode(encoding), encoding
    for bom, codec in ((codecs.BOM_UTF32_LE, "utf-32"),
                       (codecs.BOM_UTF32_BE, "utf-32"),
                       (codecs.BOM_UTF8, "utf-8-sig"),
                       (codecs.BOM_UTF16_LE, "utf-16"),
                       (codecs.BOM_UTF16_BE, "utf-16")):
        if data.startswith(bom):
            return data.decode(codec), codec
    # Detect BOM-less UTF-16 before UTF-8 (ASCII UTF-16 is valid UTF-8).
    sample = data[:8192]
    if sample and sample.count(b"\0") > len(sample) // 5:
        codec = "utf-16-le" if sample[1::2].count(0) >= sample[::2].count(0) else "utf-16-be"
        try:
            return data.decode(codec), codec
        except UnicodeError:
            pass
    try:
        return data.decode("utf-8"), "utf-8"
    except UnicodeError:
        pass
    # GBK/GB2312 are covered by GB18030, the default for downloaded novels.
    candidates = ["gb18030", "big5"]
    try:
        import chardet
        result = chardet.detect(data[:131072])
        guessed = (result.get("encoding") or "").lower()
        if guessed in ("big5", "big5hkscs") and result.get("confidence", 0) >= 0.8:
            candidates.insert(0, guessed)
    except ImportError:
        pass
    for codec in candidates:
        try:
            return data.decode(codec), codec
        except UnicodeError:
            continue
    raise ValueError("无法可靠识别编码，请在设置中手动选择文件编码后重新打开。")


def normalize_text(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\t", "    ").replace("\x00", "").lstrip("\ufeff")


class LineReader:
    def __init__(self, text, offset=0):
        self.text = normalize_text(text)
        self.offset = max(0, min(int(offset), max(0, len(self.text) - 1)))
        self.history = []
        self.chapters = find_chapters(self.text)
        self._skip_blank()

    def seek(self, offset):
        self.history.clear()
        last = len(self.text.rstrip()) - 1
        self.offset = max(0, min(int(offset), max(0, last)))
        self._skip_blank()

    def seek_percent(self, percent, width, measure):
        percent = float(str(percent).strip().rstrip("%％"))
        if not math.isfinite(percent) or not 0 <= percent <= 100:
            raise ValueError("请输入 0–100 之间的百分比，例如 35.5")
        target = round(max(0, len(self.text.rstrip()) - 1) * percent / 100)
        # Align to a visible line so a jump does not start halfway through a word.
        start = self.text.rfind("\n", 0, target) + 1
        while start < target:
            end = self.end(width, measure, start)
            if end > target or end <= start:
                break
            start = end
        self.seek(start)

    def _skip_blank(self):
        while self.offset < len(self.text) and self.text[self.offset] == "\n":
            self.offset += 1

    def end(self, width, measure, start=None):
        start = self.offset if start is None else start
        if start >= len(self.text):
            return start
        stop = self.text.find("\n", start)
        if stop < 0:
            stop = len(self.text)
        # Exponential probing keeps navigation cheap even for huge paragraphs.
        high = min(start + 64, stop)
        while high < stop and measure(self.text[start:high]) <= width:
            high = min(start + (high - start) * 2, stop)
        low = start
        while low < high:
            mid = (low + high + 1) // 2
            if measure(self.text[start:mid]) <= width:
                low = mid
            else:
                high = mid - 1
        return min(stop, max(start + 1, low))

    def line(self, width, measure):
        return self.text[self.offset:self.end(width, measure)]

    def next(self, width, measure):
        new = self.end(width, measure)
        while new < len(self.text) and self.text[new] == "\n":
            new += 1
        if new < len(self.text):
            self.history.append(self.offset)
            self.offset = new

    def previous(self, width, measure):
        if self.history:
            self.offset = self.history.pop()
            return
        target = self.offset
        if target <= 0:
            return
        last = target - 1
        while last >= 0 and self.text[last] == "\n":
            last -= 1
        if last < 0:
            return
        start = self.text.rfind("\n", 0, last + 1) + 1
        while start < target:
            end = self.end(width, measure, start)
            if end >= target or end > last:
                self.offset = start
                return
            start = end

    def reflow(self):
        self.history.clear()
