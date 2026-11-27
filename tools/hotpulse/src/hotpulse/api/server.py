"""JSON API（标准库 ThreadingHTTPServer）。

只暴露本机使用所需的只读查询与一个手动触发采集的写接口。
如果配置了 ``app.api_token``，所有 ``/api/v1/*`` 请求都需要
``Authorization: Bearer <token>``；健康检查保持公开。
"""

from __future__ import annotations

import hmac
import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import Any
from urllib.parse import parse_qs, urlsplit

from .. import __version__
from ..analysis.keywords import extract_keywords
from ..errors import HotPulseError
from ..scheduler import HotPulseService
from ..timeutil import isoformat, utcnow

logger = logging.getLogger(__name__)

MAX_BODY_BYTES = 1_000_000


class APIError(Exception):
    def __init__(self, message: str, *, status: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status = status


class HotPulseHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address: tuple[str, int], service: HotPulseService) -> None:
        self.service = service
        super().__init__(address, HotPulseRequestHandler)


class HotPulseRequestHandler(BaseHTTPRequestHandler):
    server: HotPulseHTTPServer
    protocol_version = "HTTP/1.1"
    server_version = f"HotPulse/{__version__}"

    # ------------------------------------------------------------------ verbs
    def do_GET(self) -> None:  # noqa: N802
        self._dispatch("GET")

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch("POST")

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors_headers()
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --------------------------------------------------------------- dispatch
    def _dispatch(self, method: str) -> None:
        parsed = urlsplit(self.path)
        path = parsed.path
        if path != "/" and path.endswith("/"):
            path = path[:-1]
        query = parse_qs(parsed.query, keep_blank_values=False)
        try:
            if method == "GET" and path in {"/health", "/api/v1/health"}:
                self._send_json(
                    200,
                    {
                        "status": "ok",
                        "name": "hotpulse",
                        "version": __version__,
                        "time": isoformat(utcnow()),
                    },
                )
                return
            if path.startswith("/api/v1/") and not self._authorized():
                raise APIError("Missing or invalid API token", status=401)
            if method == "GET":
                self._get(path, query)
            elif method == "POST":
                self._post(path)
            else:
                raise APIError(f"Method not allowed: {method}", status=405)
        except APIError as exc:
            self._send_json(exc.status, {"error": {"type": "request", "message": exc.message}})
        except HotPulseError as exc:
            logger.warning("API operation failed: %s", exc)
            self._send_json(
                500,
                {
                    "error": {
                        "type": type(exc).__name__,
                        "message": exc.message,
                        "remediation": exc.remediation,
                    }
                },
            )
        except (BrokenPipeError, ConnectionResetError):
            logger.debug("Client disconnected")
        except Exception as exc:  # pragma: no cover - 兜底，避免线程静默死亡
            logger.exception("Unhandled API error")
            self._send_json(
                500,
                {"error": {"type": "internal", "message": f"{type(exc).__name__}: {exc}"}},
            )

    # --------------------------------------------------------------- GET paths
    def _get(self, path: str, query: dict[str, list[str]]) -> None:
        service = self.server.service
        repo = service.repo

        if path == "/":
            self._send_json(
                200,
                {
                    "name": "HotPulse",
                    "version": __version__,
                    "description": "Layered multi-platform hot-topic aggregator",
                    "endpoints": [
                        "GET /api/v1/health",
                        "GET /api/v1/platforms",
                        "GET /api/v1/topics",
                        "GET /api/v1/history?platform=&external_id=",
                        "GET /api/v1/clusters",
                        "GET /api/v1/keywords",
                        "GET /api/v1/runs",
                        "GET /api/v1/overview",
                        "POST /api/v1/collect",
                    ],
                },
            )
            return

        if path == "/api/v1/stats":
            self._send_json(200, repo.summary())
            return

        if path == "/api/v1/platforms":
            summary = repo.summary()
            latest = {row["platform"]: row for row in summary.get("latest_runs", [])}
            platforms = []
            for name, cfg in service.config.platforms.items():
                item = {
                    "platform": name,
                    "enabled": cfg.enabled,
                    "active": name in service.collectors,
                    "limit": cfg.limit,
                    "interval_seconds": cfg.interval_seconds,
                    "weight": cfg.weight,
                    "latest_run": latest.get(name),
                }
                platforms.append(item)
            self._send_json(200, {"platforms": platforms})
            return

        if path == "/api/v1/topics":
            platform = _first(query, "platform")
            rows = repo.latest_items(
                platform=platform,
                category=_first(query, "category"),
                query=_first(query, "q") or _first(query, "query"),
                min_score=_float_query(query, "min_score"),
                max_age_hours=_float_query(query, "hours"),
                limit=_int_query(query, "limit", default=50, maximum=500),
            )
            self._send_json(
                200,
                {
                    "count": len(rows),
                    "generated_at": isoformat(utcnow()),
                    "items": rows,
                },
            )
            return

        if path == "/api/v1/history":
            platform = _required(query, "platform")
            external_id = _required(query, "external_id")
            rows = repo.history(
                platform,
                external_id,
                limit=_int_query(query, "limit", default=50, maximum=500),
            )
            self._send_json(
                200,
                {
                    "platform": platform,
                    "external_id": external_id,
                    "count": len(rows),
                    "items": rows,
                },
            )
            return

        if path == "/api/v1/clusters":
            rows = repo.latest_clusters(limit=_int_query(query, "limit", default=20, maximum=100))
            self._send_json(200, {"count": len(rows), "items": rows})
            return

        if path == "/api/v1/keywords":
            limit = _int_query(query, "limit", default=20, maximum=50)
            rows = repo.latest_items(limit=min(500, max(limit * 10, 100)))
            proxies = [
                SimpleNamespace(platform=row["platform"], title=row["title"])
                for row in rows
            ]
            keywords = extract_keywords(proxies, limit)
            self._send_json(
                200,
                {"count": len(keywords), "items": [keyword.to_dict() for keyword in keywords]},
            )
            return

        if path == "/api/v1/runs":
            rows = repo.runs(
                platform=_first(query, "platform"),
                limit=_int_query(query, "limit", default=30, maximum=200),
            )
            self._send_json(200, {"count": len(rows), "items": rows})
            return

        if path == "/api/v1/overview":
            summary = repo.summary()
            rows = repo.latest_items(limit=200)
            proxies = [
                SimpleNamespace(platform=row["platform"], title=row["title"])
                for row in rows
            ]
            self._send_json(
                200,
                {
                    "summary": summary,
                    "topics": repo.latest_items(limit=10),
                    "clusters": repo.latest_clusters(limit=10),
                    "keywords": [
                        keyword.to_dict()
                        for keyword in extract_keywords(proxies, service.config.analysis.keyword_limit)
                    ],
                    "generated_at": isoformat(utcnow()),
                },
            )
            return

        if path == "/api/v1/collect":
            raise APIError("Use POST /api/v1/collect to trigger a collection", status=405)

        raise APIError(f"Not found: {path}", status=404)

    # -------------------------------------------------------------- POST paths
    def _post(self, path: str) -> None:
        if path != "/api/v1/collect":
            raise APIError(f"Not found: {path}", status=404)
        payload = self._read_json()
        platforms = payload.get("platforms")
        if platforms is not None:
            if not isinstance(platforms, list) or not all(isinstance(item, str) for item in platforms):
                raise APIError("platforms must be a list of platform names")
        limit = payload.get("limit")
        if limit is not None:
            if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 200:
                raise APIError("limit must be an integer between 1 and 200")
        runs = self.server.service.run(platforms, limit=limit)
        self._send_json(
            200,
            {
                "generated_at": isoformat(utcnow()),
                "runs": [run.to_dict() for run in runs],
                "success": sum(1 for run in runs if run.status == "success"),
                "failed": sum(1 for run in runs if run.status == "failed"),
            },
        )

    # ----------------------------------------------------------------- helpers
    def _authorized(self) -> bool:
        token = self.server.service.config.app.api_token
        if not token:
            return True
        header = self.headers.get("Authorization", "")
        scheme, _, value = header.partition(" ")
        return scheme.lower() == "bearer" and hmac.compare_digest(value.strip(), token)

    def _read_json(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as exc:
            raise APIError("Invalid Content-Length") from exc
        if length > MAX_BODY_BYTES:
            raise APIError("Request body is too large", status=413)
        raw = self.rfile.read(length) if length else b""
        if not raw:
            return {}
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise APIError("Request body must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise APIError("Request body must be a JSON object")
        return payload

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _cors_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Authorization, Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("%s - %s", self.address_string(), fmt % args)


def create_server(
    service: HotPulseService,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> HotPulseHTTPServer:
    if not 0 <= int(port) <= 65535:
        raise ValueError("port must be between 0 and 65535")
    return HotPulseHTTPServer((host, int(port)), service)


def _first(query: dict[str, list[str]], key: str) -> str | None:
    values = query.get(key)
    return values[0].strip() if values and values[0].strip() else None


def _required(query: dict[str, list[str]], key: str) -> str:
    value = _first(query, key)
    if not value:
        raise APIError(f"Missing required query parameter: {key}")
    return value


def _int_query(
    query: dict[str, list[str]],
    key: str,
    *,
    default: int,
    maximum: int,
) -> int:
    raw = _first(query, key)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise APIError(f"{key} must be an integer") from exc
    if not 1 <= value <= maximum:
        raise APIError(f"{key} must be between 1 and {maximum}")
    return value


def _float_query(query: dict[str, list[str]], key: str) -> float | None:
    raw = _first(query, key)
    if raw is None:
        return None
    try:
        return float(raw)
    except ValueError as exc:
        raise APIError(f"{key} must be a number") from exc
