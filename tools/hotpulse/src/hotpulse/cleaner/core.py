"""清洗层：规范化、去噪、去重。

输入是采集层原始模型；输出不包含 raw 响应，只保留可入库字段。
"""

from __future__ import annotations

import hashlib
import html
import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable

from ..config import CleanerConfig
from ..models import CleanItem, CollectedItem
from ..timeutil import utcnow
from . import _text

ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200d\ufeff]")
NOISE_TITLES = {"热搜", "热搜榜", "排行榜", "热门", "推荐", "广告", "推广", "赞助"}
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


@dataclass(slots=True)
class DroppedItem:
    platform: str
    title: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {"platform": self.platform, "title": self.title, "reason": self.reason}


@dataclass(slots=True)
class CleanReport:
    items: list[CleanItem]
    dropped: list[DroppedItem] = field(default_factory=list)
    duplicate_count: int = 0
    input_count: int = 0

    @property
    def dropped_count(self) -> int:
        return len(self.dropped)

    def to_dict(self) -> dict[str, Any]:
        return {
            "input_count": self.input_count,
            "clean_count": len(self.items),
            "dropped_count": self.dropped_count,
            "duplicate_count": self.duplicate_count,
            "dropped": [item.to_dict() for item in self.dropped[:50]],
        }


class Cleaner:
    def __init__(self, config: CleanerConfig | None = None) -> None:
        self.config = config or CleanerConfig()

    def _drop(self, report: CleanReport, item: CollectedItem, reason: str) -> None:
        report.dropped.append(DroppedItem(platform=item.platform, title=item.title[:120], reason=reason))

    def _normalize_url(self, value: str) -> str:
        url = html.unescape(value or "").strip()
        if url.startswith("//"):
            url = "https:" + url
        if not url or not SCHEME_RE.match(url):
            return ""
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in {"http", "https"} or not parts.netloc:
            return ""
        # 去掉跟踪参数和 fragment，保留平台需要的查询参数。
        query = urllib.parse.parse_qsl(parts.query, keep_blank_values=False)
        filtered = [(key, val) for key, val in query if not _is_tracking_param(key)]
        return urllib.parse.urlunsplit(
            (parts.scheme, parts.netloc.lower(), parts.path or "/", urllib.parse.urlencode(filtered), "")
        )

    def fingerprint(self, item: CollectedItem, title: str) -> str:
        identity = item.external_id.strip() or item.url.strip() or title
        material = f"{item.platform}\x00{identity}\x00{title}".encode("utf-8")
        return hashlib.sha1(material).hexdigest()[:16]

    def clean(self, items: Iterable[CollectedItem], *, now: datetime | None = None) -> CleanReport:
        observed_default = now or utcnow()
        report = CleanReport(items=[])
        seen: set[str] = set()
        for item in items:
            report.input_count += 1
            title = _text.normalize_title(item.title)
            if not title:
                self._drop(report, item, "empty_title")
                continue
            if len(title) < self.config.min_title_length:
                self._drop(report, item, "too_short")
                continue
            if len(title) > self.config.max_title_length:
                self._drop(report, item, "too_long")
                continue
            if title.casefold() in NOISE_TITLES:
                self._drop(report, item, "noise")
                continue
            url = self._normalize_url(item.url)
            if not url:
                self._drop(report, item, "invalid_url")
                continue
            if self.config.drop_nsfw and bool(item.metrics.get("over_18")):
                self._drop(report, item, "nsfw")
                continue
            fingerprint = self.fingerprint(item, title)
            if fingerprint in seen:
                report.duplicate_count += 1
                self._drop(report, item, "duplicate")
                continue
            seen.add(fingerprint)
            summary = _text.normalize_summary(item.summary, self.config.max_summary_length)
            report.items.append(
                CleanItem(
                    platform=item.platform,
                    external_id=item.external_id.strip(),
                    title=title,
                    url=url,
                    rank=max(1, int(item.rank)),
                    fingerprint=fingerprint,
                    hot_value=item.hot_value,
                    author=_text.normalize_optional(item.author, 100),
                    summary=summary,
                    category_hint=_text.normalize_optional(item.category_hint, 50),
                    published_at=item.published_at,
                    observed_at=item.observed_at or observed_default,
                    metadata=_text.json_safe_metadata(item.metrics),
                )
            )
        # 防御式再按指纹去重（例如调用方传入重复对象）。
        unique: list[CleanItem] = []
        seen.clear()
        for item in report.items:
            if item.fingerprint in seen:
                report.duplicate_count += 1
                continue
            seen.add(item.fingerprint)
            unique.append(item)
        report.items = unique
        return report


def _is_tracking_param(key: str) -> bool:
    lowered = key.lower()
    return lowered.startswith("utm_") or lowered in {
        "spm",
        "from",
        "source",
        "share_source",
        "share_medium",
        "share_plat",
        "share_tag",
        "timestamp",
        "unique_k",
        "vd_source",
        "track_id",
    }


def clean_items(items: Iterable[CollectedItem], config: CleanerConfig | None = None) -> CleanReport:
    return Cleaner(config).clean(items)
