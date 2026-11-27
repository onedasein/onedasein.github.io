"""GitHub Trending 适配器（HTML 解析，无需 token）。"""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any

from ..errors import ParseError
from ..models import CollectedItem
from ..timeutil import utcnow
from ._util import collapse_ws
from .base import BaseCollector, CollectionResult

TRENDING_URL = "https://github.com/trending"
STARS_TODAY_RE = re.compile(r"([\d,]+)\s+stars?\s+today", re.IGNORECASE)


def _classes(attrs: list[tuple[str, str | None]]) -> set[str]:
    for key, value in attrs:
        if key == "class" and value:
            return set(value.split())
    return set()


class _TrendingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.entries: list[dict[str, Any]] = []
        self.current: dict[str, Any] | None = None
        self.in_article = False
        self.in_h2 = False
        self.in_desc = False
        self.in_language = False
        self.in_stargazers = False
        self.in_title = False
        self.text_buffer: list[str] = []
        self.desc_buffer: list[str] = []
        self.language_buffer: list[str] = []
        self.stargazers_buffer: list[str] = []
        self._h2_seen = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        classes = _classes(attrs)
        attr_map = {key: value for key, value in attrs}
        if tag == "article" and "Box-row" in classes:
            self.in_article = True
            self.current = {
                "repo": "",
                "description": "",
                "language": "",
                "stars_today": None,
                "total_stars": None,
                "all_text": [],
            }
            self.in_h2 = self.in_desc = self.in_language = self.in_stargazers = self.in_title = False
            self._h2_seen = False
            self.desc_buffer = []
            self.language_buffer = []
            self.stargazers_buffer = []
            return
        if not self.in_article or self.current is None:
            return
        if tag == "h2" and not self._h2_seen:
            self.in_h2 = True
            self._h2_seen = True
        elif tag == "a" and self.in_h2:
            href = str(attr_map.get("href") or "")
            if not self.current["repo"] and href.startswith("/") and href.count("/") == 2:
                self.current["repo"] = href.strip("/")
        elif tag == "p" and "color-fg-muted" in classes:
            self.in_desc = True
        elif tag == "span" and attr_map.get("itemprop") == "programmingLanguage":
            self.in_language = True
        elif tag == "a" and str(attr_map.get("href") or "").endswith("/stargazers"):
            self.in_stargazers = True
        elif tag == "a" and "Link--primary" in classes:
            self.in_title = True

    def handle_endtag(self, tag: str) -> None:
        if not self.in_article or self.current is None:
            return
        if tag == "h2":
            self.in_h2 = False
        elif tag == "p":
            self.in_desc = False
        elif tag == "span":
            self.in_language = False
        elif tag == "a":
            self.in_stargazers = False
            self.in_title = False
        elif tag == "article":
            self._finish_article()

    def handle_data(self, data: str) -> None:
        if not self.in_article or self.current is None:
            return
        text = collapse_ws(data)
        if not text:
            return
        self.current["all_text"].append(text)
        if self.in_desc:
            self.desc_buffer.append(text)
        elif self.in_language:
            self.language_buffer.append(text)
        elif self.in_stargazers:
            self.stargazers_buffer.append(text)
        elif self.in_title:
            self.text_buffer.append(text)

    def _finish_article(self) -> None:
        if self.current is None:
            return
        repo = str(self.current.get("repo") or "").strip()
        if repo:
            description = collapse_ws(" ".join(self.desc_buffer))
            language = collapse_ws(" ".join(self.language_buffer))
            combined = " ".join(self.current.get("all_text") or [])
            match = STARS_TODAY_RE.search(combined)
            stars_today = None
            if match:
                try:
                    stars_today = int(match.group(1).replace(",", ""))
                except ValueError:
                    stars_today = None
            total_stars = None
            star_text = collapse_ws(" ".join(self.stargazers_buffer))
            star_match = re.search(r"([\d,]+)", star_text)
            if star_match:
                try:
                    total_stars = int(star_match.group(1).replace(",", ""))
                except ValueError:
                    total_stars = None
            self.entries.append(
                {
                    "repo": repo,
                    "description": description,
                    "language": language,
                    "stars_today": stars_today,
                    "total_stars": total_stars,
                }
            )
        self.in_article = False
        self.current = None
        self.in_h2 = self.in_desc = self.in_language = self.in_stargazers = self.in_title = False

    def close(self) -> None:
        super().close()
        if self.in_article and self.current is not None:
            self._finish_article()


class GitHubCollector(BaseCollector):
    name = "github"
    home_url = TRENDING_URL

    def _parse_items(self, html: str, limit: int) -> list[CollectedItem]:
        parser = _TrendingParser()
        parser.feed(html)
        parser.close()
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, entry in enumerate(parser.entries[:limit], start=1):
            repo = str(entry["repo"]).strip()
            if "/" not in repo:
                continue
            owner, name = repo.split("/", 1)
            stars_today = entry.get("stars_today")
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=repo,
                    title=repo,
                    url=f"https://github.com/{owner}/{name}",
                    rank=rank,
                    hot_value=float(stars_today) if stars_today is not None else None,
                    author=owner,
                    summary=str(entry.get("description") or "").strip() or None,
                    category_hint=str(entry.get("language") or "").strip() or None,
                    observed_at=observed,
                    metrics={
                        "stars_today": stars_today,
                        "total_stars": entry.get("total_stars"),
                        "language": entry.get("language") or None,
                    },
                )
            )
        return items

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        since = str(self.platform.options.get("since") or "daily")
        params: dict[str, Any] = {"since": since}
        language = self.platform.options.get("language")
        if language:
            params["language"] = language
        response = self.http.get(TRENDING_URL, params=params, headers={"Accept": "text/html"})
        items = self._parse_items(response.text(), requested)
        if not items:
            raise ParseError(
                "GitHub trending page contained no repository entries",
                platform=self.name,
                remediation="GitHub may have changed its HTML; inspect the trending page and update parser.",
            )
        return CollectionResult(platform=self.name, items=items, source=f"trending-{since}")
