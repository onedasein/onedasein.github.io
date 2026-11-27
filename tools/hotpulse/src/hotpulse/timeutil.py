"""时间工具：内部统一使用带时区的 UTC 时间，落库使用 ISO-8601。"""

from __future__ import annotations

from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def parse_epoch(value: object) -> datetime | None:
    """解析秒/毫秒时间戳；非法值返回 None。"""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    # 13 位时间戳视为毫秒。
    if number >= 10_000_000_000:
        number /= 1000.0
    try:
        return datetime.fromtimestamp(number, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return None


def age_hours(value: datetime | None, *, now: datetime | None = None) -> float | None:
    if value is None:
        return None
    current = now or utcnow()
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    delta = (current - value.astimezone(timezone.utc)).total_seconds() / 3600.0
    return max(0.0, delta)
