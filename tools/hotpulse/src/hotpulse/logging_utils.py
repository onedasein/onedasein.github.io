"""统一日志配置。"""

from __future__ import annotations

import logging
import os


def configure_logging(level: str | None = None) -> None:
    resolved = (level or os.getenv("HOTPULSE_LOG_LEVEL") or "INFO").upper()
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s", "%Y-%m-%d %H:%M:%S")
        )
        root.addHandler(handler)
    root.setLevel(getattr(logging, resolved, logging.INFO))
    # urllib 的调试日志过于嘈杂，保留告警即可。
    logging.getLogger("urllib3").setLevel(logging.WARNING)
