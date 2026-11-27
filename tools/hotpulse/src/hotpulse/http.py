"""标准库 HTTP 客户端。

统一处理：gzip/deflate、Cookie、代理、超时、有限重试、响应体上限、
以及把 urllib 的异常转换成带 remediation 的 HttpError。
"""

from __future__ import annotations

import gzip
import http.client
import http.cookiejar
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import zlib
from dataclasses import dataclass
from typing import Any, Mapping

from .config import AppConfig
from .errors import CollectionError, HttpError

logger = logging.getLogger(__name__)

RETRY_STATUS = {429, 500, 502, 503, 504}
DEFAULT_ACCEPT = "application/json, text/html;q=0.9, */*;q=0.8"
DEFAULT_ACCEPT_LANGUAGE = "zh-CN,zh;q=0.9,en;q=0.7"


@dataclass(slots=True)
class HttpResponse:
    status: int
    url: str
    headers: Mapping[str, str]
    body: bytes

    def text(self, encoding: str | None = None) -> str:
        charset = encoding
        if charset is None:
            content_type = self.headers.get("Content-Type", "")
            for part in content_type.split(";")[1:]:
                key, _, value = part.strip().partition("=")
                if key.lower() == "charset" and value:
                    charset = value.strip("\"'")
                    break
        candidates = [charset] if charset else []
        candidates.extend(["utf-8-sig", "utf-8", "gb18030"])
        for candidate in candidates:
            if not candidate:
                continue
            try:
                return self.body.decode(candidate)
            except (LookupError, UnicodeDecodeError):
                continue
        return self.body.decode("utf-8", errors="replace")

    def json(self) -> Any:
        try:
            return json.loads(self.text())
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            snippet = self.body[:200].decode("utf-8", errors="replace")
            raise CollectionError(
                f"Expected JSON from {self.url}, got: {snippet!r}",
                remediation="The platform may be serving an HTML challenge page; retry later or use an alternate route.",
            ) from exc

    def header(self, name: str, default: str = "") -> str:
        for key, value in self.headers.items():
            if key.lower() == name.lower():
                return value
        return default


class HttpClient:
    """一个实例对应一个采集任务，Cookie 在同一实例内共享。"""

    def __init__(
        self,
        app_config: AppConfig | None = None,
        *,
        user_agent: str | None = None,
        proxy: str | None = None,
        timeout: float = 15.0,
        retries: int = 2,
        backoff: float = 1.0,
    ) -> None:
        self.app = app_config or AppConfig()
        self.user_agent = (user_agent or self.app.user_agent).strip()
        self.proxy = (proxy if proxy is not None else self.app.http_proxy).strip()
        self.timeout = timeout
        self.retries = max(1, retries)
        self.backoff = max(0.0, backoff)
        self.max_bytes = self.app.max_response_bytes
        self.cookie_jar = http.cookiejar.CookieJar()
        self._opener = self._build_opener()

    def _build_opener(self) -> urllib.request.OpenerDirector:
        handlers: list[urllib.request.BaseHandler] = [
            urllib.request.HTTPCookieProcessor(self.cookie_jar),
            urllib.request.HTTPDefaultErrorHandler(),
        ]
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}))
        else:
            handlers.append(urllib.request.ProxyHandler({}))
        return urllib.request.build_opener(*handlers)

    def _url(self, url: str, params: Mapping[str, Any] | None) -> str:
        if not params:
            return url
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None}, doseq=True)
        parts = urllib.parse.urlsplit(url)
        existing = parts.query
        merged = f"{existing}&{query}" if existing else query
        return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, merged, parts.fragment))

    def _decode(self, body: bytes, headers: Mapping[str, str], url: str) -> bytes:
        # urllib 返回的 header 名称大小写并不稳定，不能直接用 dict.get。
        encoding = next(
            (value for key, value in headers.items() if key.lower() == "content-encoding"),
            "",
        ).lower().strip()
        if not encoding or encoding == "identity":
            return body
        try:
            if "gzip" in encoding:
                return gzip.decompress(body)
            if "deflate" in encoding:
                try:
                    return zlib.decompress(body)
                except zlib.error:
                    return zlib.decompress(body, -zlib.MAX_WBITS)
        except (OSError, EOFError, zlib.error) as exc:
            raise HttpError(f"Could not decode {encoding} response from {url}", url=url) from exc
        # 未压缩或服务端返回了不支持的编码（例如 br）：保留原始字节交给上层。
        logger.debug("Unsupported content encoding %r from %s", encoding, url)
        return body

    def request(
        self,
        method: str,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
        json_body: Any = None,
        timeout: float | None = None,
        retries: int | None = None,
        raise_for_status: bool = True,
    ) -> HttpResponse:
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
        target = self._url(url, params)
        attempts = self.retries if retries is None else max(1, retries)
        request_headers = {
            "User-Agent": self.user_agent,
            "Accept": DEFAULT_ACCEPT,
            "Accept-Language": DEFAULT_ACCEPT_LANGUAGE,
            "Accept-Encoding": "gzip, deflate",
            "Connection": "close",
        }
        if data is not None:
            request_headers["Content-Type"] = "application/x-www-form-urlencoded"
        if headers:
            request_headers.update({key: value for key, value in headers.items() if value is not None})
        last_error: Exception | None = None

        for attempt in range(attempts):
            request = urllib.request.Request(target, data=data, headers=request_headers, method=method.upper())
            try:
                with self._opener.open(request, timeout=timeout or self.timeout) as response:
                    body = response.read(self.max_bytes + 1)
                    if len(body) > self.max_bytes:
                        raise CollectionError(
                            f"Response from {target} exceeds max_response_bytes={self.max_bytes}",
                            remediation="Raise app.max_response_bytes or lower the platform limit.",
                        )
                    response_headers = {k: v for k, v in response.headers.items()}
                    body = self._decode(body, response_headers, target)
                    if len(body) > self.max_bytes:
                        raise CollectionError(
                            f"Decoded response from {target} exceeds max_response_bytes={self.max_bytes}",
                            remediation="Raise app.max_response_bytes or lower the platform limit.",
                        )
                    return HttpResponse(
                        status=getattr(response, "status", 200),
                        url=response.geturl(),
                        headers=response_headers,
                        body=body,
                    )
            except urllib.error.HTTPError as exc:
                body = b""
                try:
                    body = exc.read(self.max_bytes + 1)
                except (OSError, http.client.HTTPException):
                    pass
                finally:
                    exc.close()
                status = int(exc.code)
                snippet = body[:300].decode("utf-8", errors="replace").strip()
                if status in RETRY_STATUS and attempt + 1 < attempts:
                    retry_after = exc.headers.get("Retry-After") if exc.headers else None
                    delay = self.backoff * (2**attempt)
                    try:
                        delay = max(delay, float(retry_after)) if retry_after else delay
                    except (TypeError, ValueError):
                        pass
                    logger.warning("HTTP %s from %s, retrying in %.1fs", status, target, delay)
                    time.sleep(min(delay, 10.0))
                    last_error = HttpError(
                        f"HTTP {status} from {target}",
                        status=status,
                        url=target,
                        body_snippet=snippet,
                    )
                    continue
                raise self._http_error(status, target, snippet, exc.headers) from exc
            except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
                last_error = exc
                reason = getattr(exc, "reason", exc)
                if attempt + 1 < attempts:
                    delay = self.backoff * (2**attempt)
                    logger.warning("Request to %s failed (%s), retrying in %.1fs", target, reason, delay)
                    time.sleep(min(delay, 10.0))
                    continue
                raise CollectionError(
                    f"Request to {target} failed: {reason}",
                    remediation="Check network access, proxy settings, and the platform availability.",
                ) from exc

        raise CollectionError(
            f"Request to {target} failed after {attempts} attempts: {last_error}",
            remediation="Retry later; if the failure persists, inspect docs/probe-results.json.",
        )

    def _http_error(self, status: int, url: str, snippet: str, headers: Mapping[str, str] | None) -> HttpError:
        remediation = None
        if status == 403:
            remediation = (
                "The platform rejected this IP or requires authentication. Configure the documented "
                "credentials (for Reddit: REDDIT_CLIENT_ID/SECRET) or retry from another network."
            )
        elif status == 429:
            remediation = "Rate limited. Increase the platform interval or wait before retrying."
        elif status >= 500:
            remediation = "The platform is temporarily unavailable; retry later."
        elif status == 404:
            remediation = "The endpoint may have changed; check the platform adapter and probe output."
        retry_after = None
        if headers:
            value = headers.get("Retry-After")
            if value:
                try:
                    retry_after = float(value)
                except ValueError:
                    retry_after = None
        return HttpError(
            f"HTTP {status} from {url}" + (f": {snippet[:200]}" if snippet else ""),
            status=status,
            url=url,
            body_snippet=snippet,
            retry_after=retry_after,
            remediation=remediation,
        )

    def get(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> HttpResponse:
        return self.request("POST", url, **kwargs)

    def close(self) -> None:
        try:
            self._opener.close()
        except Exception:  # pragma: no cover - 解释器退出时可能已关闭
            pass
