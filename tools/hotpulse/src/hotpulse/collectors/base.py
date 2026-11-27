"""采集层基类与统一返回结构。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from ..config import AppConfig, PlatformConfig
from ..http import HttpClient
from ..models import CollectedItem


@dataclass(slots=True)
class CollectionResult:
    platform: str
    items: list[CollectedItem]
    source: str
    warnings: list[str] = field(default_factory=list)


class BaseCollector(ABC):
    """一个适配器负责一个平台；失败时抛 CollectionError 子类。"""

    name = "base"
    # 平台页面/API 的参考页，用于构造 Referer 等请求头。
    home_url = ""

    def __init__(
        self,
        http: HttpClient,
        platform: PlatformConfig,
        app: AppConfig | None = None,
    ) -> None:
        self.http = http
        self.platform = platform
        self.app = app or AppConfig()

    @property
    def limit(self) -> int:
        return max(1, min(self.platform.limit, 200))

    @abstractmethod
    def collect(self, limit: int | None = None) -> CollectionResult:
        raise NotImplementedError

    def _requested_limit(self, limit: int | None) -> int:
        requested = self.limit if limit is None else limit
        return max(1, min(int(requested), self.limit, 200))
