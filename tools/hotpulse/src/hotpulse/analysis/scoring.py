"""评分、趋势与分类。"""

from __future__ import annotations

import math
import re
from datetime import datetime
from typing import Iterable

from ..config import AnalysisConfig
from ..models import CleanItem, PreviousSnapshot
from ..timeutil import age_hours, utcnow

# 顺序有意义：越靠前的分类优先级越高。
CATEGORY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    (
        "tech",
        (
            "人工智能", "大模型", "机器人", "算法", "编程", "开源", "科技", "数码", "芯片",
            "手机", "软件", "硬件", "互联网", "数据", "云计算", "ai", "llm", "github",
            "python", "rust", "javascript", "java", "linux", "gpu", "openai", "deepseek",
        ),
    ),
    (
        "gaming",
        (
            "游戏", "电竞", "主机", "手游", "端游", "玩家", "王者荣耀", "原神", "英雄联盟",
            "steam", "switch", "ps5", "xbox", "nintendo", "minecraft", "game",
        ),
    ),
    (
        "entertainment",
        (
            "明星", "电影", "电视剧", "综艺", "音乐", "演唱会", "娱乐", "偶像", "票房",
            "演员", "歌手", "动漫", "二次元", "导演", "剧集", "热搜", "红毯", "netflix",
        ),
    ),
    (
        "sports",
        (
            "足球", "篮球", "比赛", "冠军", "奥运", "世界杯", "球员", "体育", "乒乓",
            "网球", "nba", "cba", "英超", "西甲", "中超", "梅西", "c罗",
        ),
    ),
    (
        "finance",
        (
            "股票", "股市", "经济", "金融", "房价", "基金", "银行", "比特币", "加密",
            "美联储", "利率", "关税", "贸易", "通胀", "汇率", "财报", "上市", "融资",
        ),
    ),
    (
        "politics",
        (
            "政治", "政府", "总统", "选举", "外交", "国会", "白宫", "首相", "议会",
            "特朗普", "拜登", "普京", "欧盟", "联合国",
        ),
    ),
    (
        "society",
        (
            "社会", "警方", "通报", "事故", "法院", "判决", "民生", "政策", "城市",
            "疫情", "天气", "灾害", "救援", "失联", "调查", "回应", "网友",
        ),
    ),
    (
        "health",
        ("健康", "医疗", "医院", "疾病", "病毒", "药物", "医生", "癌症", "减肥", "睡眠"),
    ),
    (
        "education",
        ("教育", "学校", "高考", "大学", "学生", "老师", "考研", "留学", "考试", "课程"),
    ),
    (
        "lifestyle",
        ("美食", "旅游", "穿搭", "生活", "家居", "宠物", "情感", "婚姻", "租房", "咖啡"),
    ),
]
ENGLISH_WORD_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{1,}")


def _contains(text: str, keyword: str) -> bool:
    if keyword.isascii():
        return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
    return keyword in text


def classify(item: CleanItem, platform_hint: str | None = None) -> str:
    text = " ".join(
        part
        for part in (
            item.title,
            item.summary or "",
            item.category_hint or "",
            platform_hint or "",
        )
        if part
    ).casefold()
    for category, keywords in CATEGORY_PATTERNS:
        if any(_contains(text, keyword.casefold()) for keyword in keywords):
            return category
    return "other"


def compute_score(
    item: CleanItem,
    *,
    max_rank: int,
    max_hot: float,
    config: AnalysisConfig,
    platform_weight: float,
    now: datetime,
) -> float:
    rank_span = max(1, max_rank - 1)
    rank_component = 1.0 - (max(1, item.rank) - 1) / rank_span
    rank_component = max(0.0, min(1.0, rank_component))

    if item.hot_value is not None and item.hot_value > 0 and max_hot > 0:
        heat_component = math.log1p(item.hot_value) / math.log1p(max_hot)
        heat_component = max(0.0, min(1.0, heat_component))
    else:
        heat_component = 0.0

    if item.published_at is None:
        recency_component = 0.5
    else:
        age = age_hours(item.published_at, now=now) or 0.0
        recency_component = math.pow(0.5, age / max(config.half_life_hours, 0.1))
        recency_component = max(0.0, min(1.0, recency_component))

    total_weight = config.rank_weight + config.heat_weight + config.recency_weight
    if total_weight <= 0:
        total_weight = 1.0
    base = (
        rank_component * config.rank_weight
        + heat_component * config.heat_weight
        + recency_component * config.recency_weight
    ) / total_weight
    score = base * 100.0 * max(0.01, platform_weight)
    return round(max(0.0, min(100.0, score)), 2)


def compute_trend(
    item: CleanItem,
    previous: PreviousSnapshot | None,
) -> tuple[str, int | None, float | None]:
    if previous is None:
        return "new", None, None
    rank_delta = previous.rank - item.rank
    if item.hot_value is not None and previous.hot_value is not None:
        heat_delta = item.hot_value - previous.hot_value
    else:
        heat_delta = None
    if item.rank < previous.rank:
        trend = "rising"
    elif item.rank > previous.rank:
        trend = "falling"
    else:
        trend = "steady"
    return trend, rank_delta, heat_delta


def category_counts(items: Iterable[CleanItem]) -> list[dict[str, object]]:
    counts: dict[str, int] = {}
    for item in items:
        counts[item.category_hint or "other"] = counts.get(item.category_hint or "other", 0) + 1
    return [{"category": key, "count": value} for key, value in sorted(counts.items(), key=lambda kv: -kv[1])]
