"""平台注册表：把配置里的平台名映射到适配器。"""

from __future__ import annotations

from ..config import AppConfig, Config, PlatformConfig
from ..http import HttpClient
from .base import BaseCollector
from .bilibili import BilibiliCollector
from .douyin import DouyinCollector
from .github import GitHubCollector
from .reddit import RedditCollector
from .tieba import TiebaCollector
from .zhihu import ZhihuCollector

COLLECTORS: dict[str, type[BaseCollector]] = {
    "bilibili": BilibiliCollector,
    "zhihu": ZhihuCollector,
    "douyin": DouyinCollector,
    "tieba": TiebaCollector,
    "reddit": RedditCollector,
    "github": GitHubCollector,
}


def create_collector(
    name: str,
    platform: PlatformConfig,
    app: AppConfig,
    *,
    http: HttpClient | None = None,
    retries: int = 2,
    backoff: float = 1.0,
) -> BaseCollector:
    try:
        collector_cls = COLLECTORS[name]
    except KeyError as exc:
        raise ValueError(f"Unknown platform: {name}") from exc
    client = http or HttpClient(
        app,
        timeout=platform.timeout_seconds,
        retries=retries,
        backoff=backoff,
    )
    return collector_cls(client, platform, app)


def create_configured_collectors(config: Config) -> dict[str, BaseCollector]:
    collectors: dict[str, BaseCollector] = {}
    for name, platform in config.platforms.items():
        if not platform.enabled:
            continue
        if name not in COLLECTORS:
            continue
        collectors[name] = create_collector(
            name,
            platform,
            config.app,
            retries=config.scheduler.retry_attempts,
            backoff=config.scheduler.retry_backoff_seconds,
        )
    return collectors
