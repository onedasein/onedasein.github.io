"""无第三方分词器的关键词降级方案。

中文用 2–4 字 n-gram，英文用单词；按“出现该词的不同主题数”计数，
并奖励跨平台出现的词。MVP 目标是可解释的候选词，不是语言学最优解。
"""

from __future__ import annotations

import re
from collections import defaultdict
from typing import Iterable

from ..models import Keyword, ScoredItem

CHINESE_RE = re.compile(r"[\u4e00-\u9fff]+")
ENGLISH_RE = re.compile(r"[a-zA-Z][a-zA-Z0-9+#.-]{2,}")
STOPWORDS = {
    "一个", "一种", "一些", "什么", "为什么", "怎么", "如何", "我们", "他们", "你们",
    "这个", "那个", "这些", "那些", "没有", "可以", "可能", "已经", "还是", "就是",
    "不是", "真的", "这么", "那么", "因为", "所以", "但是", "如果", "以及", "并且",
    "对于", "关于", "通过", "进行", "表示", "认为", "目前", "现在", "今日", "最新",
    "视频", "网友", "回应", "曝光", "官方", "热搜", "热门", "话题", "事件", "中国",
    "美国", "全球", "世界", "宣布", "发布", "开始", "结束", "首次", "再次",
    "the", "and", "for", "are", "but", "not", "you", "all", "can", "her", "was",
    "one", "our", "out", "day", "get", "has", "him", "his", "how", "man", "new",
    "now", "old", "see", "two", "way", "who", "boy", "did", "its", "let", "put",
    "say", "she", "too", "use", "that", "with", "have", "this", "will", "your",
    "from", "they", "know", "want", "been", "good", "much", "some", "time", "very",
    "when", "come", "here", "just", "like", "long", "make", "many", "more", "only",
    "over", "such", "take", "than", "them", "well", "were", "what", "with", "would",
}


def _candidates(text: str) -> set[str]:
    lowered = text.casefold()
    found: set[str] = set()
    for sequence in CHINESE_RE.findall(lowered):
        length = len(sequence)
        if 2 <= length <= 4:
            found.add(sequence)
        for n in (2, 3, 4):
            if length < n:
                continue
            for index in range(length - n + 1):
                gram = sequence[index : index + n]
                if gram not in STOPWORDS:
                    found.add(gram)
    for word in ENGLISH_RE.findall(lowered):
        if word not in STOPWORDS:
            found.add(word)
    return {term for term in found if term and term not in STOPWORDS}


def extract_keywords(items: Iterable[ScoredItem], limit: int = 20) -> list[Keyword]:
    counts: dict[str, int] = defaultdict(int)
    platforms: dict[str, set[str]] = defaultdict(set)
    for item in items:
        terms = _candidates(item.title)
        for term in terms:
            counts[term] += 1
            platforms[term].add(item.platform)
    ranked: list[Keyword] = []
    for term, count in counts.items():
        if count < 2:
            continue
        platform_set = platforms[term]
        score = count * (1.0 + 0.35 * (len(platform_set) - 1)) * (1.0 + min(len(term), 6) / 20.0)
        ranked.append(Keyword(term=term, count=count, platforms=tuple(sorted(platform_set)), score=score))
    ranked.sort(key=lambda keyword: (-keyword.score, -keyword.count, keyword.term))
    # 去掉被更高分长词完全包含的短词（例如“人工智能”已选中时不再展示“人工”）。
    selected: list[Keyword] = []
    for keyword in ranked:
        if any(keyword.term != other.term and keyword.term in other.term for other in selected[:limit]):
            continue
        selected.append(keyword)
        if len(selected) >= max(1, limit):
            break
    return selected
