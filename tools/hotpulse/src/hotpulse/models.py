"""跨层数据模型。

采集层输出 CollectedItem；清洗层输出 CleanItem；分析层输出 ScoredItem。
存储层只消费 ScoredItem，不依赖平台实现。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .timeutil import isoformat, utcnow


@dataclass(slots=True)
class CollectedItem:
    platform: str
    external_id: str
    title: str
    url: str
    rank: int
    hot_value: float | None = None
    author: str | None = None
    summary: str | None = None
    category_hint: str | None = None
    published_at: datetime | None = None
    observed_at: datetime = field(default_factory=utcnow)
    metrics: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class CleanItem:
    platform: str
    external_id: str
    title: str
    url: str
    rank: int
    fingerprint: str
    hot_value: float | None = None
    author: str | None = None
    summary: str | None = None
    category_hint: str | None = None
    published_at: datetime | None = None
    observed_at: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ScoredItem:
    platform: str
    external_id: str
    title: str
    url: str
    rank: int
    fingerprint: str
    score: float
    trend: str = "new"
    category: str = "other"
    hot_value: float | None = None
    rank_delta: int | None = None
    heat_delta: float | None = None
    author: str | None = None
    summary: str | None = None
    published_at: datetime | None = None
    observed_at: datetime = field(default_factory=utcnow)
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_clean(
        cls,
        item: CleanItem,
        *,
        score: float,
        trend: str,
        category: str,
        rank_delta: int | None,
        heat_delta: float | None,
    ) -> "ScoredItem":
        return cls(
            platform=item.platform,
            external_id=item.external_id,
            title=item.title,
            url=item.url,
            rank=item.rank,
            fingerprint=item.fingerprint,
            score=score,
            trend=trend,
            category=category,
            hot_value=item.hot_value,
            rank_delta=rank_delta,
            heat_delta=heat_delta,
            author=item.author,
            summary=item.summary,
            published_at=item.published_at,
            observed_at=item.observed_at,
            metadata=dict(item.metadata),
        )


@dataclass(frozen=True, slots=True)
class PreviousSnapshot:
    rank: int
    hot_value: float | None
    score: float | None
    observed_at: str | None = None


@dataclass(slots=True)
class Keyword:
    term: str
    count: int
    platforms: tuple[str, ...]
    score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "count": self.count,
            "platforms": list(self.platforms),
            "score": round(self.score, 3),
        }


@dataclass(slots=True)
class Cluster:
    """跨平台同题聚合结果。"""

    cluster_id: str
    title: str
    score: float
    item_count: int
    updated_at: datetime = field(default_factory=utcnow)
    members: list[ScoredItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "title": self.title,
            "score": round(self.score, 2),
            "item_count": self.item_count,
            "updated_at": isoformat(self.updated_at),
            "members": [
                {
                    "platform": member.platform,
                    "external_id": member.external_id,
                    "title": member.title,
                    "url": member.url,
                    "score": round(member.score, 2),
                    "trend": member.trend,
                    "category": member.category,
                }
                for member in self.members
            ],
        }


@dataclass(slots=True)
class RunResult:
    platform: str
    status: str
    item_count: int = 0
    duration_ms: int = 0
    run_id: int | None = None
    source: str | None = None
    error: str | None = None
    dropped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "platform": self.platform,
            "status": self.status,
            "item_count": self.item_count,
            "duration_ms": self.duration_ms,
            "run_id": self.run_id,
            "source": self.source,
            "error": self.error,
            "dropped": self.dropped,
        }


def item_to_dict(item: ScoredItem | CleanItem) -> dict[str, Any]:
    """存储层/报告层共用的扁平字典，避免依赖 dataclass 反射。"""
    return {
        "platform": item.platform,
        "external_id": item.external_id,
        "title": item.title,
        "url": item.url,
        "rank": item.rank,
        "fingerprint": item.fingerprint,
        "score": getattr(item, "score", None),
        "trend": getattr(item, "trend", None),
        "category": getattr(item, "category", None),
        "hot_value": item.hot_value,
        "rank_delta": getattr(item, "rank_delta", None),
        "heat_delta": getattr(item, "heat_delta", None),
        "author": item.author,
        "summary": item.summary,
        "published_at": isoformat(item.published_at),
        "observed_at": isoformat(item.observed_at),
        "metadata": item.metadata,
    }
