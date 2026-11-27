"""配置加载：TOML + 环境变量，零第三方依赖。

相对数据库路径按启动时的工作目录解析；配置文件默认读取
``config/hotpulse.toml``，找不到时使用内置默认值。
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any

from .errors import ConfigError

DEFAULT_USER_AGENT = "HotPulse/0.1 (local research hot-topic aggregator)"


@dataclass(slots=True)
class AppConfig:
    database: str = "data/hotpulse.db"
    log_level: str = "INFO"
    user_agent: str = DEFAULT_USER_AGENT
    api_token: str = ""
    http_proxy: str = ""
    max_response_bytes: int = 8_000_000


@dataclass(slots=True)
class SchedulerConfig:
    default_interval_seconds: int = 600
    max_workers: int = 4
    retry_attempts: int = 2
    retry_backoff_seconds: float = 1.5
    jitter_seconds: int = 5


@dataclass(slots=True)
class CleanerConfig:
    min_title_length: int = 2
    max_title_length: int = 300
    max_summary_length: int = 600
    drop_nsfw: bool = True


@dataclass(slots=True)
class AnalysisConfig:
    half_life_hours: float = 24.0
    rank_weight: float = 0.55
    heat_weight: float = 0.30
    recency_weight: float = 0.15
    stale_after_hours: float = 24.0
    keyword_limit: int = 20


@dataclass(slots=True)
class PlatformConfig:
    enabled: bool = True
    limit: int = 50
    interval_seconds: int = 600
    weight: float = 1.0
    timeout_seconds: float = 15.0
    min_interval_seconds: int = 60
    options: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Config:
    app: AppConfig = field(default_factory=AppConfig)
    scheduler: SchedulerConfig = field(default_factory=SchedulerConfig)
    cleaner: CleanerConfig = field(default_factory=CleanerConfig)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    platforms: dict[str, PlatformConfig] = field(default_factory=dict)
    base_dir: str = ""
    source_path: str | None = None

    def platform(self, name: str) -> PlatformConfig:
        try:
            return self.platforms[name]
        except KeyError as exc:
            raise ConfigError(f"Unknown platform: {name}") from exc

    def enabled_platforms(self) -> list[str]:
        return [name for name, cfg in self.platforms.items() if cfg.enabled]

    def platform_weights(self) -> dict[str, float]:
        return {name: cfg.weight for name, cfg in self.platforms.items()}

    def public_dict(self) -> dict[str, Any]:
        return {
            "app": {
                "database": self.app.database,
                "log_level": self.app.log_level,
                "user_agent": self.app.user_agent,
                "http_proxy": bool(self.app.http_proxy),
                "api_token_configured": bool(self.app.api_token),
                "max_response_bytes": self.app.max_response_bytes,
            },
            "scheduler": {
                "max_workers": self.scheduler.max_workers,
                "retry_attempts": self.scheduler.retry_attempts,
                "retry_backoff_seconds": self.scheduler.retry_backoff_seconds,
                "jitter_seconds": self.scheduler.jitter_seconds,
            },
            "analysis": {
                "half_life_hours": self.analysis.half_life_hours,
                "stale_after_hours": self.analysis.stale_after_hours,
                "rank_weight": self.analysis.rank_weight,
                "heat_weight": self.analysis.heat_weight,
                "recency_weight": self.analysis.recency_weight,
            },
            "platforms": {
                name: {
                    "enabled": cfg.enabled,
                    "limit": cfg.limit,
                    "interval_seconds": cfg.interval_seconds,
                    "weight": cfg.weight,
                    "options": cfg.options,
                }
                for name, cfg in self.platforms.items()
            },
            "source_path": self.source_path,
        }


def _default_platforms() -> dict[str, PlatformConfig]:
    return {
        "bilibili": PlatformConfig(limit=50, interval_seconds=300, weight=1.0),
        "zhihu": PlatformConfig(limit=50, interval_seconds=300, weight=1.0),
        "douyin": PlatformConfig(limit=50, interval_seconds=300, weight=1.1),
        "tieba": PlatformConfig(limit=50, interval_seconds=600, weight=0.9),
        "reddit": PlatformConfig(limit=50, interval_seconds=600, weight=1.0),
        "github": PlatformConfig(limit=25, interval_seconds=900, weight=1.0, options={"since": "daily"}),
    }


def default_config() -> Config:
    return Config(platforms=_default_platforms())


def _read_toml(path: Path) -> dict[str, Any]:
    try:
        with path.open("rb") as handle:
            raw = tomllib.load(handle)
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"Invalid TOML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Config root must be a table: {path}")
    return raw


def _as_int(value: Any, key: str) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be an integer") from exc


def _as_float(value: Any, key: str) -> float:
    if isinstance(value, bool):
        raise ConfigError(f"{key} must be a number")
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ConfigError(f"{key} must be a number") from exc


def _as_bool(value: Any, key: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false", "1", "0"}:
        return value.lower() in {"true", "1"}
    raise ConfigError(f"{key} must be a boolean")


def _as_text(value: Any, key: str) -> str:
    if not isinstance(value, str):
        raise ConfigError(f"{key} must be a string")
    return value.strip()


def _apply_table(target: Any, raw: dict[str, Any], prefix: str) -> None:
    for key, value in raw.items():
        attr = key
        if not hasattr(target, attr):
            # 未知字段忽略，便于向前兼容；拼写错误由用户通过文档排查。
            continue
        full = f"{prefix}.{key}"
        current = getattr(target, attr)
        if isinstance(current, bool):
            setattr(target, attr, _as_bool(value, full))
        elif isinstance(current, int):
            setattr(target, attr, _as_int(value, full))
        elif isinstance(current, float):
            setattr(target, attr, _as_float(value, full))
        elif isinstance(current, str):
            setattr(target, attr, _as_text(value, full))
        else:
            setattr(target, attr, value)


def _apply_platforms(config: Config, raw: dict[str, Any]) -> None:
    for name, values in raw.items():
        if not isinstance(values, dict):
            raise ConfigError(f"platforms.{name} must be a table")
        base = config.platforms.get(name, PlatformConfig())
        base = replace(base, options=dict(base.options))
        _apply_table(base, values, f"platforms.{name}")
        options = values.get("options")
        if options is not None:
            if not isinstance(options, dict):
                raise ConfigError(f"platforms.{name}.options must be a table")
            base.options = {str(k): v for k, v in options.items()}
        config.platforms[name] = base


def _apply_env(config: Config, base_dir: Path) -> None:
    env_map = {
        "HOTPULSE_DB": ("app", "database"),
        "HOTPULSE_LOG_LEVEL": ("app", "log_level"),
        "HOTPULSE_USER_AGENT": ("app", "user_agent"),
        "HOTPULSE_API_TOKEN": ("app", "api_token"),
        "HOTPULSE_HTTP_PROXY": ("app", "http_proxy"),
    }
    for env_name, (section, attr) in env_map.items():
        value = os.getenv(env_name)
        if value is not None:
            setattr(getattr(config, section), attr, value.strip())

    if os.getenv("HOTPULSE_MAX_RESPONSE_BYTES"):
        config.app.max_response_bytes = _as_int(
            os.getenv("HOTPULSE_MAX_RESPONSE_BYTES"), "HOTPULSE_MAX_RESPONSE_BYTES"
        )

    disabled = os.getenv("HOTPULSE_DISABLE_PLATFORMS", "")
    for name in (part.strip() for part in disabled.split(",")):
        if name and name in config.platforms:
            config.platforms[name].enabled = False

    # 允许用环境变量覆盖单平台开关，便于容器部署。
    for name, platform in config.platforms.items():
        env_name = f"HOTPULSE_{name.upper()}_ENABLED"
        value = os.getenv(env_name)
        if value is not None:
            platform.enabled = _as_bool(value, env_name)


def _resolve_database(config: Config, base_dir: Path) -> None:
    database = config.app.database.strip()
    if not database:
        raise ConfigError("app.database must not be empty")
    if database == ":memory:":
        config.app.database = database
        return
    path = Path(database).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    config.app.database = str(path.resolve())


def validate_config(config: Config) -> None:
    if config.scheduler.max_workers < 1 or config.scheduler.max_workers > 32:
        raise ConfigError("scheduler.max_workers must be between 1 and 32")
    if config.scheduler.retry_attempts < 1 or config.scheduler.retry_attempts > 10:
        raise ConfigError("scheduler.retry_attempts must be between 1 and 10")
    if config.scheduler.retry_backoff_seconds < 0:
        raise ConfigError("scheduler.retry_backoff_seconds must be >= 0")
    if config.scheduler.jitter_seconds < 0:
        raise ConfigError("scheduler.jitter_seconds must be >= 0")
    if config.cleaner.min_title_length < 1:
        raise ConfigError("cleaner.min_title_length must be >= 1")
    if config.cleaner.max_title_length < config.cleaner.min_title_length:
        raise ConfigError("cleaner.max_title_length must be >= min_title_length")
    if config.cleaner.max_summary_length < 0:
        raise ConfigError("cleaner.max_summary_length must be >= 0")
    if config.analysis.half_life_hours <= 0:
        raise ConfigError("analysis.half_life_hours must be > 0")
    if config.analysis.stale_after_hours <= 0:
        raise ConfigError("analysis.stale_after_hours must be > 0")
    for key in ("rank_weight", "heat_weight", "recency_weight"):
        if getattr(config.analysis, key) < 0:
            raise ConfigError(f"analysis.{key} must be >= 0")
    if config.analysis.rank_weight + config.analysis.heat_weight + config.analysis.recency_weight <= 0:
        raise ConfigError("analysis weights must not all be zero")
    if not 1 <= config.analysis.keyword_limit <= 100:
        raise ConfigError("analysis.keyword_limit must be between 1 and 100")
    if config.app.max_response_bytes < 1024:
        raise ConfigError("app.max_response_bytes must be >= 1024")
    for name, platform in config.platforms.items():
        if not 1 <= platform.limit <= 200:
            raise ConfigError(f"platforms.{name}.limit must be between 1 and 200")
        if platform.interval_seconds < 5:
            raise ConfigError(f"platforms.{name}.interval_seconds must be >= 5")
        if platform.timeout_seconds <= 0:
            raise ConfigError(f"platforms.{name}.timeout_seconds must be > 0")
        if platform.weight <= 0:
            raise ConfigError(f"platforms.{name}.weight must be > 0")
        if not isinstance(platform.options, dict):
            raise ConfigError(f"platforms.{name}.options must be a table")


def load_config(
    path: str | Path | None = None,
    *,
    base_dir: str | Path | None = None,
) -> Config:
    """加载配置。显式路径不存在时报错；默认路径不存在时使用内置默认值。"""
    base = Path(base_dir or Path.cwd()).resolve()
    config = default_config()
    config.base_dir = str(base)

    explicit = path or os.getenv("HOTPULSE_CONFIG")
    candidate: Path | None = None
    if explicit:
        candidate = Path(explicit).expanduser()
        if not candidate.is_absolute():
            candidate = base / candidate
        if not candidate.exists():
            raise ConfigError(f"Config file not found: {candidate}")
    else:
        default_path = base / "config" / "hotpulse.toml"
        if default_path.exists():
            candidate = default_path

    if candidate is not None:
        raw = _read_toml(candidate)
        for section, target in (
            ("app", config.app),
            ("scheduler", config.scheduler),
            ("cleaner", config.cleaner),
            ("analysis", config.analysis),
        ):
            values = raw.get(section, {})
            if not isinstance(values, dict):
                raise ConfigError(f"{section} must be a table")
            _apply_table(target, values, section)
        platform_values = raw.get("platforms", {})
        if not isinstance(platform_values, dict):
            raise ConfigError("platforms must be a table")
        _apply_platforms(config, platform_values)
        config.source_path = str(candidate.resolve())

    _apply_env(config, base)
    _resolve_database(config, base)
    validate_config(config)
    return config
