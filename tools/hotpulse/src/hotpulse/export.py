"""静态数据导出：把数据库中的最新快照整理成博客/看板可直接消费的 JSON。

这一层刻意不依赖采集器或网络，只读取 Repository。因此可以在构建博客数据、
做离线快照或审计时安全调用。导出格式带 ``schema_version``，博客端可以据此
做兼容处理；字段保持扁平、稳定，避免把 SQLite 表结构泄漏到展示层。
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from typing import Any

from . import __version__
from .analysis.keywords import extract_keywords
from .config import Config
from .errors import ConfigError
from .storage import Repository
from .timeutil import isoformat, utcnow

EXPORT_SCHEMA_VERSION = 1
MAX_EXPORT_LIMIT = 500

PLATFORM_META: dict[str, dict[str, str]] = {
    "bilibili": {"label": "Bilibili", "short": "B站", "color": "#00a1d6", "icon": "tv"},
    "zhihu": {"label": "知乎", "short": "知乎", "color": "#056de8", "icon": "question"},
    "douyin": {"label": "抖音", "short": "抖音", "color": "#fe2c55", "icon": "music"},
    "tieba": {"label": "贴吧", "short": "贴吧", "color": "#4e6ef2", "icon": "comments"},
    "reddit": {"label": "Reddit", "short": "Reddit", "color": "#ff4500", "icon": "alien"},
    "github": {"label": "GitHub", "short": "GitHub", "color": "#8b5cf6", "icon": "code-branch"},
}

CATEGORY_META: dict[str, str] = {
    "tech": "科技",
    "gaming": "游戏",
    "entertainment": "娱乐",
    "sports": "体育",
    "finance": "财经",
    "politics": "时政",
    "society": "社会",
    "health": "健康",
    "education": "教育",
    "lifestyle": "生活",
    "other": "其他",
}

TREND_META = {
    "new": "新上榜",
    "rising": "升温",
    "steady": "持平",
    "falling": "降温",
}


def build_export(
    config: Config,
    repository: Repository,
    *,
    limit: int = 100,
    platform: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """生成博客看板数据。

    Args:
        config: 用于平台顺序、权重与展示名；不会写入配置。
        repository: 已初始化的存储层。
        limit: 最多导出的主题数（1..500）。
        platform: 只导出某个平台；仍会保留其他平台的空状态。
        now: 生成时间，测试时可固定。
    """
    limit = max(1, min(int(limit), MAX_EXPORT_LIMIT))
    if platform is not None:
        if platform not in config.platforms:
            raise ConfigError(
                f"Unknown platform: {platform}",
                remediation=f"Choose one of: {', '.join(config.platforms)}",
            )

    generated_at = now or utcnow()
    summary = repository.summary()
    rows = repository.latest_items(platform=platform, limit=limit)
    clusters = repository.latest_clusters(limit=12)
    runs = repository.runs(limit=30)
    keyword_proxies = [
        SimpleNamespace(platform=row["platform"], title=row["title"])
        for row in rows
    ]
    keywords = extract_keywords(keyword_proxies, min(20, config.analysis.keyword_limit))
    topics = [_topic_payload(row) for row in rows]
    platforms = _platform_payloads(config, summary, topics)
    category_counts = _category_counts(topics)
    trend_counts = _trend_counts(topics)
    recent_runs = [_run_payload(row) for row in runs[:12]]

    data_through = max((row.get("observed_at") or "" for row in rows), default=None) or None
    active_platforms = sum(1 for item in platforms if item["count"] > 0)
    return {
        "schema_version": EXPORT_SCHEMA_VERSION,
        "generated_at": isoformat(generated_at),
        "data_through": data_through,
        "source": {
            "name": "HotPulse",
            "version": __version__,
            "description": "Layered multi-platform hot-topic aggregator",
        },
        "stats": {
            "topics": len(topics),
            "total_topics": int(summary["topics"]),
            "snapshots": int(summary["snapshots"]),
            "runs": int(summary["runs"]),
            "platforms": len(platforms),
            "active_platforms": active_platforms,
            "average_score": round(sum(item["score"] for item in topics) / len(topics), 2) if topics else 0.0,
            "max_score": max((item["score"] for item in topics), default=0.0),
        },
        "trends": trend_counts,
        "categories": category_counts,
        "platforms": platforms,
        "topics": topics,
        "keywords": [keyword.to_dict() for keyword in keywords],
        "clusters": [_cluster_payload(cluster) for cluster in clusters],
        "recent_runs": recent_runs,
        "filter": {"platform": platform, "limit": limit},
    }


def _topic_payload(row: dict[str, Any]) -> dict[str, Any]:
    platform = str(row["platform"])
    meta = _platform_meta(platform)
    category = str(row.get("category") or "other")
    return {
        "platform": platform,
        "platform_label": meta["label"],
        "platform_short": meta["short"],
        "platform_color": meta["color"],
        "external_id": str(row["external_id"]),
        "title": str(row.get("title") or ""),
        "url": str(row.get("url") or ""),
        "rank": int(row.get("rank") or 0),
        "hot_value": _number(row.get("hot_value")),
        "score": round(float(row.get("score") or 0.0), 2),
        "trend": str(row.get("trend") or "new"),
        "trend_label": TREND_META.get(str(row.get("trend") or "new"), "未知"),
        "category": category,
        "category_label": CATEGORY_META.get(category, "其他"),
        "observed_at": row.get("observed_at"),
    }


def _platform_payloads(
    config: Config,
    summary: dict[str, Any],
    topics: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stats_by_platform = {row["platform"]: row for row in summary.get("platforms", [])}
    runs_by_platform = {row["platform"]: row for row in summary.get("latest_runs", [])}
    topics_by_platform: dict[str, list[dict[str, Any]]] = {}
    for item in topics:
        topics_by_platform.setdefault(item["platform"], []).append(item)

    payloads: list[dict[str, Any]] = []
    for name, cfg in config.platforms.items():
        meta = _platform_meta(name)
        items = topics_by_platform.get(name, [])
        stat = stats_by_platform.get(name, {})
        last_run = runs_by_platform.get(name)
        payloads.append(
            {
                "key": name,
                **meta,
                "enabled": bool(cfg.enabled),
                "weight": cfg.weight,
                "count": len(items),
                "last_seen": stat.get("last_seen"),
                "last_run": _run_payload(last_run) if last_run else None,
                "top": items[:5],
            }
        )
    return payloads


def _category_counts(topics: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    for item in topics:
        key = str(item["category"])
        counts[key] = counts.get(key, 0) + 1
    ordered = sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))
    return [
        {"key": key, "label": CATEGORY_META.get(key, "其他"), "count": count}
        for key, count in ordered
    ]


def _trend_counts(topics: list[dict[str, Any]]) -> dict[str, int]:
    counts = {key: 0 for key in TREND_META}
    for item in topics:
        key = str(item["trend"])
        if key in counts:
            counts[key] += 1
    return counts


def _cluster_payload(cluster: dict[str, Any]) -> dict[str, Any]:
    members = []
    for member in cluster.get("members", []):
        meta = _platform_meta(str(member["platform"]))
        members.append(
            {
                "platform": member["platform"],
                "platform_label": meta["label"],
                "platform_color": meta["color"],
                "external_id": member.get("external_id"),
                "title": member.get("title"),
                "url": member.get("url"),
                "score": round(float(member.get("score") or 0.0), 2),
            }
        )
    return {
        "cluster_id": cluster.get("cluster_id"),
        "title": cluster.get("title"),
        "score": round(float(cluster.get("score") or 0.0), 2),
        "item_count": int(cluster.get("item_count") or 0),
        "updated_at": cluster.get("updated_at"),
        "members": members,
    }


def _run_payload(run: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": run.get("id"),
        "platform": run.get("platform"),
        "status": run.get("status"),
        "item_count": int(run.get("item_count") or 0),
        "duration_ms": int(run.get("duration_ms") or 0),
        "started_at": run.get("started_at"),
        "finished_at": run.get("finished_at"),
        "source": run.get("source"),
    }


def _platform_meta(name: str) -> dict[str, str]:
    return PLATFORM_META.get(
        name,
        {"label": name.title(), "short": name.title(), "color": "#64748b", "icon": "circle"},
    )


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
