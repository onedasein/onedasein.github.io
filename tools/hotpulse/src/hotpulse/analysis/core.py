"""分析层入口：输入清洗后条目，输出分数、趋势、分类、关键词与跨平台聚合。"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from ..config import AnalysisConfig
from ..models import CleanItem, Cluster, Keyword, PreviousSnapshot, ScoredItem
from ..timeutil import utcnow
from .clusters import build_clusters
from .keywords import extract_keywords
from .scoring import classify, compute_score, compute_trend


@dataclass(slots=True)
class AnalysisResult:
    items: list[ScoredItem]
    keywords: list[Keyword] = field(default_factory=list)
    clusters: list[Cluster] = field(default_factory=list)
    category_counts: list[dict[str, object]] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "item_count": len(self.items),
            "keywords": [keyword.to_dict() for keyword in self.keywords],
            "clusters": [cluster.to_dict() for cluster in self.clusters],
            "category_counts": self.category_counts,
        }


class AnalysisEngine:
    def __init__(
        self,
        config: AnalysisConfig | None = None,
        platform_weights: Mapping[str, float] | None = None,
    ) -> None:
        self.config = config or AnalysisConfig()
        self.platform_weights = dict(platform_weights or {})

    def analyze(
        self,
        items: list[CleanItem],
        previous: Mapping[str, Mapping[str, PreviousSnapshot]] | None = None,
        *,
        now: datetime | None = None,
        platform_weights: Mapping[str, float] | None = None,
    ) -> AnalysisResult:
        timestamp = now or utcnow()
        previous = previous or {}
        weights = dict(self.platform_weights)
        if platform_weights:
            weights.update(platform_weights)
        by_platform: dict[str, list[CleanItem]] = {}
        for item in items:
            by_platform.setdefault(item.platform, []).append(item)

        scored: list[ScoredItem] = []
        for platform, platform_items in by_platform.items():
            max_rank = max((item.rank for item in platform_items), default=1)
            hot_values = [item.hot_value for item in platform_items if item.hot_value and item.hot_value > 0]
            max_hot = max(hot_values, default=0.0)
            platform_weight = max(0.01, float(weights.get(platform, 1.0)))
            prior = previous.get(platform, {})
            for item in platform_items:
                previous_item = prior.get(item.external_id)
                score = compute_score(
                    item,
                    max_rank=max_rank,
                    max_hot=max_hot,
                    config=self.config,
                    platform_weight=platform_weight,
                    now=timestamp,
                )
                trend, rank_delta, heat_delta = compute_trend(item, previous_item)
                scored.append(
                    ScoredItem.from_clean(
                        item,
                        score=score,
                        trend=trend,
                        category=classify(item),
                        rank_delta=rank_delta,
                        heat_delta=heat_delta,
                    )
                )

        scored.sort(key=lambda item: (-item.score, item.platform, item.rank))
        keywords = extract_keywords(scored, self.config.keyword_limit)
        clusters = build_clusters(scored, now=timestamp)
        category_counter = Counter(item.category for item in scored)
        categories = [
            {"category": category, "count": count}
            for category, count in category_counter.most_common()
        ]
        return AnalysisResult(items=scored, keywords=keywords, clusters=clusters, category_counts=categories)


def analyze_items(
    items: list[CleanItem],
    config: AnalysisConfig | None = None,
    previous: Mapping[str, Mapping[str, PreviousSnapshot]] | None = None,
    platform_weights: Mapping[str, float] | None = None,
) -> AnalysisResult:
    return AnalysisEngine(config, platform_weights).analyze(items, previous)
