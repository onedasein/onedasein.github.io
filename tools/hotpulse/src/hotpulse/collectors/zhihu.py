"""知乎热榜适配器。"""

from __future__ import annotations

import logging
import re
from typing import Any

from ..errors import CollectionError, HotPulseError, ParseError
from ..models import CollectedItem
from ..timeutil import parse_epoch, utcnow
from ._util import safe_int, truncate
from .base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)

PRIMARY_URL = "https://api.zhihu.com/topstory/hot-list"
FALLBACK_URL = "https://www.zhihu.com/api/v3/feed/topstory/hot-list-web"
HOME_URL = "https://www.zhihu.com/hot"
HEAT_RE = re.compile(r"([\d.]+)\s*(万|亿)?\s*热度")


class ZhihuCollector(BaseCollector):
    name = "zhihu"
    home_url = HOME_URL

    def _headers(self) -> dict[str, str]:
        return {
            "Referer": "https://www.zhihu.com/hot",
            "Accept": "application/json, text/plain, */*",
        }

    def _parse_heat(self, text: str) -> float | None:
        match = HEAT_RE.search(text or "")
        if not match:
            return None
        try:
            number = float(match.group(1))
        except ValueError:
            return None
        unit = match.group(2)
        if unit == "万":
            number *= 10_000
        elif unit == "亿":
            number *= 100_000_000
        return number

    def _parse_items(self, data: list[Any], limit: int) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, wrapper in enumerate(data[:limit], start=1):
            if not isinstance(wrapper, dict):
                continue
            target = wrapper.get("target") if isinstance(wrapper.get("target"), dict) else wrapper
            title = str(target.get("title") or "").strip()
            if not title:
                continue
            raw_url = str(target.get("url") or target.get("link") or "").strip()
            question_id = target.get("id")
            if question_id is None:
                match = re.search(r"/questions?/(\d+)", raw_url)
                question_id = match.group(1) if match else None
            external_id = str(question_id or raw_url).strip()
            if not external_id:
                continue
            url = f"https://www.zhihu.com/question/{question_id}" if question_id else raw_url
            detail_text = str(wrapper.get("detail_text") or target.get("detail_text") or "").strip()
            summary = str(target.get("excerpt") or target.get("description") or "").strip()
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=external_id,
                    title=title,
                    url=url,
                    rank=rank,
                    hot_value=self._parse_heat(detail_text),
                    author=str(target.get("author") or "").strip() or None,
                    summary=truncate(summary, 600) or None,
                    published_at=parse_epoch(target.get("created") or target.get("created_time")),
                    observed_at=observed,
                    metrics={
                        "answer_count": safe_int(target.get("answer_count")),
                        "follower_count": safe_int(target.get("follower_count")),
                        "comment_count": safe_int(target.get("comment_count")),
                        "detail_text": detail_text,
                    },
                )
            )
        return items

    def _load(self, url: str, params: dict[str, Any], source: str, limit: int) -> CollectionResult:
        response = self.http.get(url, params=params, headers=self._headers())
        payload = response.json()
        data = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(data, list):
            raise ParseError(f"Zhihu {source} returned no data list", platform=self.name)
        items = self._parse_items(data, limit)
        if not items:
            raise ParseError(f"Zhihu {source} returned no usable items", platform=self.name)
        return CollectionResult(platform=self.name, items=items, source=source)

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        errors: list[str] = []
        try:
            return self._load(PRIMARY_URL, {"limit": requested}, "hot-list", requested)
        except HotPulseError as exc:
            errors.append(f"hot-list: {exc}")
            logger.warning("Zhihu primary endpoint failed, trying web fallback: %s", exc)
        try:
            return self._load(
                FALLBACK_URL,
                {"limit": min(requested, 50), "desktop": "true"},
                "hot-list-web",
                requested,
            )
        except HotPulseError as exc:
            errors.append(f"hot-list-web: {exc}")
        raise CollectionError(
            "Zhihu collection failed; " + " | ".join(errors),
            platform=self.name,
            remediation="Zhihu may require a browser cookie or has rate-limited this IP; retry later.",
        )
