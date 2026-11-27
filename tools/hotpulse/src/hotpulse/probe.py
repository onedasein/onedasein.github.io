"""可行性探针：不写数据库，直接验证六个平台的采集路由。"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Sequence

from .collectors import create_collector
from .config import Config
from .errors import AuthRequiredError, CollectionError, HotPulseError, HttpError
from .http import HttpClient
from .timeutil import isoformat, utcnow


def _status_for(exc: BaseException) -> str:
    if isinstance(exc, AuthRequiredError):
        return "needs_credentials"
    if isinstance(exc, HttpError):
        if exc.status == 403:
            return "blocked"
        if exc.status in {429, 503}:
            return "rate_limited"
        return "failed"
    if isinstance(exc, CollectionError):
        return "failed"
    return "error"


def _probe_one(config: Config, name: str, limit: int) -> dict[str, Any]:
    platform = config.platform(name)
    client = HttpClient(
        config.app,
        timeout=min(platform.timeout_seconds, 12.0),
        retries=1,
        backoff=0.5,
    )
    collector = create_collector(name, platform, config.app, http=client)
    started = time.monotonic()
    try:
        result = collector.collect(limit)
        latency = int((time.monotonic() - started) * 1000)
        samples = [
            {
                "rank": item.rank,
                "title": item.title,
                "hot_value": item.hot_value,
                "url": item.url,
            }
            for item in result.items[:3]
        ]
        return {
            "platform": name,
            "status": "success" if result.items else "empty",
            "source": result.source,
            "item_count": len(result.items),
            "latency_ms": latency,
            "samples": samples,
            "warnings": list(result.warnings),
        }
    except HotPulseError as exc:
        return {
            "platform": name,
            "status": _status_for(exc),
            "item_count": 0,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": str(exc)[:800],
            "remediation": exc.remediation,
        }
    except Exception as exc:  # 探针要报告未知异常而不是中断整组
        return {
            "platform": name,
            "status": "error",
            "item_count": 0,
            "latency_ms": int((time.monotonic() - started) * 1000),
            "error": f"{type(exc).__name__}: {exc}"[:800],
        }
    finally:
        client.close()


def run_probe(
    config: Config,
    platforms: Sequence[str] | None = None,
    *,
    limit: int = 3,
) -> dict[str, Any]:
    if limit < 1 or limit > 20:
        raise ValueError("probe limit must be between 1 and 20")
    if platforms is None:
        selected = config.enabled_platforms()
    else:
        selected = list(dict.fromkeys(platforms))
        for name in selected:
            config.platform(name)  # 未知平台在这里抛 ConfigError
    if not selected:
        raise ValueError("no platforms selected")
    workers = max(1, min(len(selected), 6))
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hotpulse-probe") as pool:
        results = list(pool.map(lambda name: _probe_one(config, name, limit), selected))
    summary: dict[str, int] = {}
    for result in results:
        status = str(result["status"])
        summary[status] = summary.get(status, 0) + 1
    return {
        "generated_at": isoformat(utcnow()),
        "config": config.source_path or "(built-in defaults)",
        "limit": limit,
        "summary": summary,
        "platforms": results,
    }
