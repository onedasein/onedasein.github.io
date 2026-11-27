"""清洗层文本与 JSON 安全工具。"""

from __future__ import annotations

import html
import json
import re
from typing import Any

from ..collectors._util import collapse_ws, strip_html, truncate

ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\ufeff]")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def normalize_title(value: str | None) -> str:
    if not value:
        return ""
    text = html.unescape(value)
    text = ZERO_WIDTH_RE.sub("", text)
    text = CONTROL_RE.sub("", text)
    return collapse_ws(text)


def normalize_summary(value: str | None, max_length: int) -> str | None:
    if not value or max_length <= 0:
        return None
    text = normalize_title(strip_html(value))
    if not text:
        return None
    return truncate(text, max_length)


def normalize_optional(value: str | None, max_length: int) -> str | None:
    if not value:
        return None
    text = normalize_title(value)
    return truncate(text, max_length) if text else None


def json_safe_metadata(value: Any) -> dict[str, Any]:
    """确保 metadata 可被 json.dumps 编码，并限制嵌套规模。"""
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, val in list(value.items())[:50]:
        key_text = str(key)[:80]
        if isinstance(val, (str, int, float, bool)) or val is None:
            cleaned[key_text] = truncate(val, 500) if isinstance(val, str) else val
        elif isinstance(val, (list, tuple)):
            cleaned[key_text] = [
                truncate(str(item), 120) if isinstance(item, str) else item
                for item in list(val)[:20]
                if isinstance(item, (str, int, float, bool)) or item is None
            ]
        else:
            try:
                json.dumps(val)
                cleaned[key_text] = val
            except (TypeError, ValueError):
                cleaned[key_text] = truncate(str(val), 200)
    return cleaned
