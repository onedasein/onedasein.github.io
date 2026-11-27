"""采集层共用的小型解析工具。"""

from __future__ import annotations

import html
import re
from html.parser import HTMLParser

_NUMBER_RE = re.compile(r"([\d][\d,]*(?:\.\d+)?)\s*(万|亿|w|k)?", re.IGNORECASE)


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        if data.strip():
            self.parts.append(data.strip())

    def get_text(self) -> str:
        return " ".join(self.parts)


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    parser = _TextExtractor()
    try:
        parser.feed(value)
        parser.close()
    except Exception:  # HTMLParser 对畸形输入通常不会抛，但保持降级路径
        return collapse_ws(html.unescape(re.sub(r"<[^>]+>", " ", value)))
    return collapse_ws(parser.get_text())


def collapse_ws(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", html.unescape(value)).strip()


def truncate(value: str, limit: int) -> str:
    if limit <= 0:
        return ""
    if len(value) <= limit:
        return value
    return value[: max(0, limit - 1)].rstrip() + "…"


def safe_int(value: object, default: int = 0) -> int:
    if value is None or isinstance(value, bool):
        return default
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def parse_human_number(value: object) -> float | None:
    """解析 "1.2万"、"12,345"、"3k" 之类的展示数字。"""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = _NUMBER_RE.search(str(value).replace(",", ""))
    if not match:
        return None
    try:
        number = float(match.group(1))
    except ValueError:
        return None
    unit = (match.group(2) or "").lower()
    multiplier = {"万": 10_000, "w": 10_000, "亿": 100_000_000, "k": 1_000}.get(unit, 1)
    return number * multiplier


def first_present(*values: object) -> object | None:
    for value in values:
        if value is not None and value != "":
            return value
    return None
