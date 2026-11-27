"""抖音热榜适配器。"""

from __future__ import annotations

import urllib.parse
from typing import Any

from ..errors import ParseError
from ..models import CollectedItem
from ..timeutil import parse_epoch, utcnow
from ._util import safe_int
from .base import BaseCollector, CollectionResult

HOT_URL = "https://www.douyin.com/aweme/v1/web/hot/search/list/"
HOME_URL = "https://www.douyin.com/"


class DouyinCollector(BaseCollector):
    name = "douyin"
    home_url = HOME_URL

    def _headers(self) -> dict[str, str]:
        return {
            "Referer": "https://www.douyin.com/",
            "Accept": "application/json, text/plain, */*",
        }

    def _entries(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise ParseError("Douyin returned an unexpected payload", platform=self.name)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ParseError("Douyin response has no data object", platform=self.name)
        entries: list[dict[str, Any]] = []
        seen: set[str] = set()
        for key in ("word_list", "trending_list"):
            values = data.get(key)
            if not isinstance(values, list):
                continue
            for value in values:
                if not isinstance(value, dict):
                    continue
                word = str(value.get("word") or "").strip()
                if not word or word in seen:
                    continue
                seen.add(word)
                entries.append(value)
        return entries

    def _parse_items(self, entries: list[dict[str, Any]], limit: int) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        observed = utcnow()
        for index, raw in enumerate(entries[:limit]):
            word = str(raw.get("word") or "").strip()
            if not word:
                continue
            position = safe_int(raw.get("position"), default=index)
            external_id = str(
                raw.get("sentence_id") or raw.get("group_id") or raw.get("word_id") or word
            ).strip()
            hot_value = raw.get("hot_value")
            try:
                hot_number = float(hot_value) if hot_value is not None else None
            except (TypeError, ValueError):
                hot_number = None
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=external_id,
                    title=word,
                    url=f"https://www.douyin.com/search/{urllib.parse.quote(word)}",
                    rank=position + 1,
                    hot_value=hot_number,
                    summary=None,
                    published_at=parse_epoch(raw.get("event_time")),
                    observed_at=observed,
                    metrics={
                        "video_count": safe_int(raw.get("video_count")),
                        "discuss_video_count": safe_int(raw.get("discuss_video_count")),
                        "label": raw.get("label"),
                    },
                )
            )
        return items

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        response = self.http.get(
            HOT_URL,
            params={
                "device_platform": "webapp",
                "aid": 6383,
                "channel": "channel_pc_web",
                "detail_list": 1,
            },
            headers=self._headers(),
        )
        entries = self._entries(response.json())
        if not entries:
            raise ParseError("Douyin hot search returned no words", platform=self.name)
        return CollectionResult(
            platform=self.name,
            items=self._parse_items(entries, requested),
            source="hot-search",
        )
