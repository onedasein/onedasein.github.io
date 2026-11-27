"""Reddit r/popular/hot 适配器。

路由顺序：OAuth（client_credentials）→ 公开 JSON → Atom RSS。
没有凭据时仍尝试公开路由；若全部被拒，抛出 AuthRequiredError 并在
remediation 中说明需要设置 REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET。
"""

from __future__ import annotations

import base64
import logging
import os
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any

from ..errors import AuthRequiredError, CollectionError, HotPulseError, ParseError
from ..models import CollectedItem
from ..timeutil import parse_epoch, parse_iso, utcnow
from ._util import safe_int, strip_html, truncate
from .base import BaseCollector, CollectionResult

logger = logging.getLogger(__name__)

TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_URL = "https://oauth.reddit.com/r/popular/hot"
PUBLIC_URL = "https://www.reddit.com/r/popular/hot.json"
RSS_URL = "https://www.reddit.com/r/popular/hot/.rss"
ATOM_NS = {"a": "http://www.w3.org/2005/Atom"}


class RedditCollector(BaseCollector):
    name = "reddit"

    def _credentials(self) -> tuple[str, str] | None:
        client_id = os.getenv("REDDIT_CLIENT_ID", "").strip()
        client_secret = os.getenv("REDDIT_CLIENT_SECRET", "").strip()
        if client_id and client_secret:
            return client_id, client_secret
        return None

    def _parse_listing(self, payload: Any, limit: int) -> list[CollectedItem]:
        if not isinstance(payload, dict):
            raise ParseError("Reddit returned an unexpected payload", platform=self.name)
        listing = payload.get("data")
        children = listing.get("children") if isinstance(listing, dict) else None
        if not isinstance(children, list):
            raise ParseError("Reddit response has no data.children list", platform=self.name)
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, child in enumerate(children[:limit], start=1):
            if not isinstance(child, dict):
                continue
            data = child.get("data")
            if not isinstance(data, dict):
                continue
            title = str(data.get("title") or "").strip()
            external_id = str(data.get("id") or data.get("name") or "").strip()
            if not title or not external_id:
                continue
            permalink = str(data.get("permalink") or "").strip()
            if permalink.startswith("/"):
                url = f"https://www.reddit.com{permalink}"
            else:
                url = str(data.get("url") or "").strip() or f"https://www.reddit.com/comments/{external_id}"
            score = data.get("score")
            try:
                hot_value = float(score) if score is not None else None
            except (TypeError, ValueError):
                hot_value = None
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=external_id,
                    title=title,
                    url=url,
                    rank=rank,
                    hot_value=hot_value,
                    author=str(data.get("author") or "").strip() or None,
                    summary=truncate(str(data.get("selftext") or "").strip(), 600) or None,
                    category_hint=str(data.get("subreddit") or "").strip() or None,
                    published_at=parse_epoch(data.get("created_utc")),
                    observed_at=observed,
                    metrics={
                        "subreddit": data.get("subreddit"),
                        "num_comments": safe_int(data.get("num_comments")),
                        "upvote_ratio": data.get("upvote_ratio"),
                        "over_18": bool(data.get("over_18")),
                    },
                )
            )
        return items

    def _oauth(self, limit: int) -> CollectionResult:
        credentials = self._credentials()
        if credentials is None:
            raise AuthRequiredError(
                "Reddit OAuth credentials are not configured",
                platform=self.name,
                remediation="Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET (script app) to use OAuth.",
            )
        client_id, client_secret = credentials
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode("utf-8")).decode("ascii")
        token_response = self.http.post(
            TOKEN_URL,
            data=urllib.parse.urlencode({"grant_type": "client_credentials"}).encode("utf-8"),
            headers={
                "Authorization": f"Basic {basic}",
                "Accept": "application/json",
                "Content-Type": "application/x-www-form-urlencoded",
            },
            retries=1,
        )
        token_payload = token_response.json()
        token = token_payload.get("access_token") if isinstance(token_payload, dict) else None
        if not token:
            error = token_payload.get("error") if isinstance(token_payload, dict) else None
            raise ParseError(
                f"Reddit OAuth token response has no access_token{f' ({error})' if error else ''}",
                platform=self.name,
                remediation="Verify the Reddit script app credentials and that the app type is 'script'.",
            )
        response = self.http.get(
            OAUTH_URL,
            params={"limit": limit, "raw_json": 1},
            headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
            retries=1,
        )
        items = self._parse_listing(response.json(), limit)
        if not items:
            raise ParseError("Reddit OAuth listing returned no items", platform=self.name)
        return CollectionResult(platform=self.name, items=items, source="oauth")

    def _public(self, limit: int) -> CollectionResult:
        response = self.http.get(
            PUBLIC_URL,
            params={"limit": limit, "raw_json": 1},
            headers={"Accept": "application/json"},
            retries=1,
        )
        items = self._parse_listing(response.json(), limit)
        if not items:
            raise ParseError("Reddit public listing returned no items", platform=self.name)
        return CollectionResult(platform=self.name, items=items, source="public-json")

    def _rss(self, limit: int) -> CollectionResult:
        response = self.http.get(
            RSS_URL,
            params={"limit": limit},
            headers={"Accept": "application/atom+xml, application/xml;q=0.9"},
            retries=1,
        )
        try:
            root = ET.fromstring(response.body)
        except ET.ParseError as exc:
            raise ParseError(
                f"Reddit RSS is not valid XML: {exc}",
                platform=self.name,
                remediation="Reddit may be serving an HTML block page; configure OAuth credentials.",
            ) from exc
        entries = root.findall(".//a:entry", ATOM_NS)
        if not entries:
            entries = root.findall(".//entry")
        items: list[CollectedItem] = []
        observed = utcnow()
        for rank, entry in enumerate(entries[:limit], start=1):
            title = (entry.findtext("a:title", default="", namespaces=ATOM_NS) or "").strip()
            if not title:
                continue
            link = entry.find("a:link", ATOM_NS)
            href = link.get("href") if link is not None else ""
            link_id = (entry.findtext("a:id", default="", namespaces=ATOM_NS) or "").strip()
            external_id = link_id[3:] if link_id.startswith("t3_") else link_id
            if not external_id:
                external_id = href.rsplit("/comments/", 1)[-1].split("/", 1)[0]
            if not external_id:
                continue
            author = entry.findtext("a:author/a:name", default="", namespaces=ATOM_NS) or ""
            updated = entry.findtext("a:updated", default="", namespaces=ATOM_NS) or ""
            content = entry.findtext("a:content", default="", namespaces=ATOM_NS) or ""
            category = entry.find("a:category", ATOM_NS)
            subreddit = category.get("term") if category is not None else None
            items.append(
                CollectedItem(
                    platform=self.name,
                    external_id=external_id,
                    title=strip_html(title),
                    url=href or f"https://www.reddit.com/comments/{external_id}",
                    rank=rank,
                    hot_value=None,
                    author=author.strip() or None,
                    summary=truncate(strip_html(content), 600) or None,
                    category_hint=subreddit,
                    published_at=parse_iso(updated),
                    observed_at=observed,
                    metrics={"source": "rss", "subreddit": subreddit},
                )
            )
        if not items:
            raise ParseError("Reddit RSS returned no entries", platform=self.name)
        return CollectionResult(platform=self.name, items=items, source="rss")

    def collect(self, limit: int | None = None) -> CollectionResult:
        requested = self._requested_limit(limit)
        credentials = self._credentials() is not None
        errors: list[str] = []
        routes = [("oauth", self._oauth), ("public-json", self._public), ("rss", self._rss)]
        for label, route in routes:
            try:
                return route(requested)
            except HotPulseError as exc:
                errors.append(f"{label}: {exc}")
                logger.warning("Reddit route %s failed: %s", label, exc)
        message = "Reddit collection failed; " + " | ".join(errors)
        if not credentials:
            raise AuthRequiredError(
                message,
                platform=self.name,
                remediation=(
                    "Reddit blocks this network without authentication. Create a Reddit script app, "
                    "set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET, then retry."
                ),
            )
        raise CollectionError(
            message,
            platform=self.name,
            remediation="Check the OAuth app credentials and Reddit API availability.",
        )
