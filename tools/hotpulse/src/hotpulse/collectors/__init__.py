"""采集层：每个平台一个适配器，统一输出 CollectedItem。"""

from .base import BaseCollector, CollectionResult
from .bilibili import BilibiliCollector
from .douyin import DouyinCollector
from .github import GitHubCollector
from .reddit import RedditCollector
from .registry import COLLECTORS, create_collector, create_configured_collectors
from .tieba import TiebaCollector
from .zhihu import ZhihuCollector

__all__ = [
    "BaseCollector",
    "CollectionResult",
    "BilibiliCollector",
    "ZhihuCollector",
    "DouyinCollector",
    "TiebaCollector",
    "RedditCollector",
    "GitHubCollector",
    "COLLECTORS",
    "create_collector",
    "create_configured_collectors",
]
