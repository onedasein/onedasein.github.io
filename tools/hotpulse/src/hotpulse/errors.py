"""领域异常。

各层只抛出本模块定义的异常，API/CLI 负责把它们转换成用户可见信息。
"""

from __future__ import annotations


class HotPulseError(Exception):
    """所有可预期错误的基类。"""

    def __init__(self, message: str, *, remediation: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.remediation = remediation

    def __str__(self) -> str:
        if self.remediation:
            return f"{self.message} Remediation: {self.remediation}"
        return self.message


class ConfigError(HotPulseError):
    """配置文件或环境变量不合法。"""


class StorageError(HotPulseError):
    """SQLite 读写失败。"""


class CollectionError(HotPulseError):
    """采集层失败。"""

    def __init__(
        self,
        message: str,
        *,
        platform: str | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message, remediation=remediation)
        self.platform = platform


class ParseError(CollectionError):
    """响应格式与适配器预期不符。"""


class AuthRequiredError(CollectionError):
    """平台要求凭据，但当前实例没有配置。"""


class HttpError(CollectionError):
    """HTTP 请求失败，保留状态码和响应片段用于诊断。"""

    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        url: str | None = None,
        body_snippet: str = "",
        retry_after: float | None = None,
        remediation: str | None = None,
    ) -> None:
        super().__init__(message, remediation=remediation)
        self.status = status
        self.url = url
        self.body_snippet = body_snippet
        self.retry_after = retry_after
