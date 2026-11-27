"""跨平台同题聚合：标题 token Jaccard + 包含关系，union-find。"""

from __future__ import annotations

import hashlib
import re
from collections import defaultdict
from datetime import datetime
from typing import Iterable

from ..models import Cluster, ScoredItem
from ..timeutil import utcnow

PUNCT_RE = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
ENGLISH_RE = re.compile(r"[a-z][a-z0-9+#.-]{1,}")
MIN_SIMILARITY = 0.42


def _tokens(title: str) -> set[str]:
    text = title.casefold()
    tokens: set[str] = set(ENGLISH_RE.findall(text))
    for sequence in CHINESE_RE.findall(text):
        if len(sequence) <= 2:
            tokens.add(sequence)
            continue
        for index in range(len(sequence) - 1):
            tokens.add(sequence[index : index + 2])
    return tokens


def _normalized(title: str) -> str:
    return PUNCT_RE.sub("", title.casefold())


def _similar(a: ScoredItem, b: ScoredItem, tokens_a: set[str], tokens_b: set[str]) -> bool:
    if a.platform == b.platform:
        return False
    norm_a, norm_b = _normalized(a.title), _normalized(b.title)
    if norm_a and norm_b:
        if norm_a == norm_b:
            return True
        shorter, longer = sorted((norm_a, norm_b), key=len)
        if len(shorter) >= 6 and shorter in longer:
            return True
    if not tokens_a or not tokens_b:
        return False
    intersection = len(tokens_a & tokens_b)
    if intersection < 2:
        return False
    union = len(tokens_a | tokens_b)
    return union > 0 and intersection / union >= MIN_SIMILARITY


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, value: int) -> int:
        while self.parent[value] != value:
            self.parent[value] = self.parent[self.parent[value]]
            value = self.parent[value]
        return value

    def union(self, left: int, right: int) -> None:
        root_left, root_right = self.find(left), self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            root_left, root_right = root_right, root_left
        self.parent[root_right] = root_left
        if self.rank[root_left] == self.rank[root_right]:
            self.rank[root_left] += 1


def build_clusters(items: Iterable[ScoredItem], *, now: datetime | None = None) -> list[Cluster]:
    materialized = list(items)
    if len(materialized) < 2:
        return []
    tokens = [_tokens(item.title) for item in materialized]
    union = _UnionFind(len(materialized))
    for left in range(len(materialized)):
        for right in range(left + 1, len(materialized)):
            if _similar(materialized[left], materialized[right], tokens[left], tokens[right]):
                union.union(left, right)

    groups: dict[int, list[ScoredItem]] = defaultdict(list)
    for index, item in enumerate(materialized):
        groups[union.find(index)].append(item)

    timestamp = now or utcnow()
    clusters: list[Cluster] = []
    for members in groups.values():
        platforms = {member.platform for member in members}
        if len(platforms) < 2:
            continue
        members.sort(key=lambda member: (-member.score, member.platform, member.rank))
        cluster_key = "|".join(sorted(f"{member.platform}:{member.external_id}" for member in members))
        cluster_id = hashlib.sha1(cluster_key.encode("utf-8")).hexdigest()[:16]
        average = sum(member.score for member in members) / len(members)
        score = min(100.0, average + 6.0 * (len(platforms) - 1))
        clusters.append(
            Cluster(
                cluster_id=cluster_id,
                title=members[0].title,
                score=round(score, 2),
                item_count=len(members),
                updated_at=timestamp,
                members=members,
            )
        )
    clusters.sort(key=lambda cluster: (-cluster.score, -cluster.item_count, cluster.cluster_id))
    return clusters
