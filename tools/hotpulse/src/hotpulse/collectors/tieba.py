"""百度贴吧热议榜适配器。"""

from __future__ import annotations

import html
from typing import Any

from ..errors import ParseError
from ..models import CollectedItem
from ..timeutil import parse_epoch, utcnow
from ._util import first_present, parse_human_number, strip_html, truncate
from .base import BaseCollector, CollectionResult

TOPIC_LIST_URL = "https://tieba.baidu.com/hottopic/browse/topicList"
HOME_URL = "https://tieba.baidu.com/"


class TiebaCollector(BaseCollector):
    name = "tieba"
    home_url = HOME_URL

    def _headers(self) -> dict[str, str]:
        return {
            "Referer": "https://tieba.baidu.com/",
            "Accept": "application/json, text/plain, */*",
        }

    def _entries(self, payload: Any) -> list[dict[str, Any]]:
        if not isinstance(payload, dict):
            raise ParseError("Tieba returned an unexpected payload", platform=self.name)
        data = payload.get("data")
        if not isinstance(data, dict):
            raise ParseError("Tieba response has no data object", platform=self.name)
        bang_topic = data.get("bang_topic")
        entries = bang_topic.get("topic_list") if isinstance(bang_topic, dict) else data.get("topic_list")
        if not isinstance(entries, list):
            raise ParseError("Tieba response has no topic list", platform=self.name)
        return [entry for entry in entries if isinstance(entry, dict)]

    def _parse_items(self, entries: list[dict[str, Any]], limit: int) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, raw in enumerate(entries[:limit], start=1):
            title = strip_html(str(first_present(raw.get("topic_name"), raw.get("title")) or ""))
            if not title:
                continue
            topic_id = str(raw.get("topic_id") or raw.get("id") or "").strip()
            if not topic_id:
                continue
            topic_url = str(raw.get("topic_url") or "").strip()
            topic_url = html.unescape(topic_url) if topic_url else ""
            if not topic_url:
                topic_url = f"https://tieba.baidu.com/hottopic/browse/hottopic?topic_id={topic_id}"
            summary = strip_html(
                str(first_present(raw.get("topic_desc"), raw.get("abstract"), raw.get("desc")) or "")
            )
            tag = raw.get("tag")
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=topic_id,
                    title=title,
                    url=topic_url,
                    rank=rank,
                    hot_value=parse_human_number(raw.get("discuss_num")),
                    summary=truncate(summary, 600) or None,
                    category_hint=str(tag).strip() if isinstance(tag, (str, int)) and str(tag).strip() else None,
                    published_at=parse_epoch(raw.get("create_time")),
                    observed_at=observed,
                    metrics={
                        "discuss_num": raw.get("discuss_num"),
                        "idx_num": raw.get("idx_num"),
                    },
                )
            )
        return items

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        response = self.http.get(TOPIC_LIST_URL, headers=self._headers())
        entries = self._entries(response.json())
        if not entries:
            raise ParseError("Tieba hot topic list is empty", platform=self.name)
        return CollectionResult(
            platform=self.name,
            items=self._parse_items(entries, requested),
            source="topicList",
        )
