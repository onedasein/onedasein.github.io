"""Bilibili 综合热门/排行榜适配器。"""

from __future__ import annotations

import logging
from typing import Any

from ..errors import CollectionError, HotPulseError, ParseError
from ..models import CollectedItem
from ..timeutil import parse_epoch, utcnow
from ._util import safe_int, truncate
from .base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)

RANKING_URL = "https://api.bilibili.com/x/web-interface/ranking/v2"
POPULAR_URL = "https://api.bilibili.com/x/web-interface/popular"
HOME_URL = "https://www.bilibili.com/"


class BilibiliCollector(BaseCollector):
    name = "bilibili"
    home_url = HOME_URL

    def _headers(self) -> dict[str, str]:
        return {"Referer": "https://www.bilibili.com/", "Origin": "https://www.bilibili.com"}

    def _prime_cookie(self, *, force: bool = False) -> None:
        if not force and any(cookie.name == "buvid3" for cookie in self.http.cookie_jar):
            return
        try:
            self.http.get(HOME_URL, headers=self._headers(), retries=1, raise_for_status=False)
        except HotPulseError as exc:
            # Cookie 获取失败不阻塞请求；API 可能在无 Cookie 时仍可访问。
            logger.debug("Bilibili cookie prime failed: %s", exc)

    def _load(self, url: str, params: dict[str, Any], source: str, limit: int) -> CollectionResult | None:
        response = self.http.get(url, params=params, headers=self._headers())
        payload = response.json()
        if not isinstance(payload, dict):
            raise ParseError(f"Bilibili returned an unexpected payload ({source})", platform=self.name)
        code = safe_int(payload.get("code"), default=0)
        if code != 0:
            raise ParseError(
                f"Bilibili {source} returned code={code}: {payload.get('message') or payload.get('msg') or ''}",
                platform=self.name,
                remediation="The API may require a fresh cookie or has changed; retry and check probe output.",
            )
        data = payload.get("data") or {}
        items = self._parse_items(data.get("list") or [], limit)
        if not items:
            raise ParseError(f"Bilibili {source} returned no items", platform=self.name)
        return CollectionResult(platform=self.name, items=items, source=source)

    def _parse_items(self, raw_items: list[Any], limit: int) -> list[CollectedItem]:
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, raw in enumerate(raw_items[:limit], start=1):
            if not isinstance(raw, dict):
                continue
            bvid = str(raw.get("bvid") or "").strip()
            title = str(raw.get("title") or "").strip()
            if not bvid or not title:
                continue
            stat = raw.get("stat") if isinstance(raw.get("stat"), dict) else {}
            owner = raw.get("owner") if isinstance(raw.get("owner"), dict) else {}
            metrics = {
                "view": safe_int(stat.get("view")),
                "like": safe_int(stat.get("like")),
                "reply": safe_int(stat.get("reply")),
                "danmaku": safe_int(stat.get("danmaku")),
                "favorite": safe_int(stat.get("favorite")),
                "coin": safe_int(stat.get("coin")),
                "share": safe_int(stat.get("share")),
            }
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=bvid,
                    title=title,
                    url=f"https://www.bilibili.com/video/{bvid}",
                    rank=rank,
                    hot_value=float(metrics["view"] or 0) or None,
                    author=str(owner.get("name") or "").strip() or None,
                    summary=truncate(str(raw.get("desc") or "").strip(), 600) or None,
                    category_hint=str(raw.get("tname") or "").strip() or None,
                    published_at=parse_epoch(raw.get("pubdate")),
                    observed_at=observed,
                    metrics=metrics,
                )
            )
        return items

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        self._prime_cookie()
        errors: list[str] = []
        try:
            result = self._load(RANKING_URL, {"rid": 0, "type": "all"}, "ranking", requested)
            if result:
                return result
        except HotPulseError as exc:
            errors.append(f"ranking: {exc}")
            logger.warning("Bilibili ranking failed, trying popular: %s", exc)
            # code -352 通常意味着 Cookie 失效，重新预热后再试 fallback。
            self._prime_cookie(force=True)

        try:
            result = self._load(POPULAR_URL, {"ps": requested, "pn": 1}, "popular", requested)
            if result:
                return result
        except HotPulseError as exc:
            errors.append(f"popular: {exc}")

        raise CollectionError(
            "Bilibili collection failed; " + " | ".join(errors),
            platform=self.name,
            remediation="Check bilibili.com availability and whether its web API/cookie requirements changed.",
        )
