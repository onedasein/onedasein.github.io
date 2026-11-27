"""调度器：按平台 interval 决定何时执行，并保持进程常驻。"""

from __future__ import annotations

import logging
import random
import threading
from datetime import datetime, timedelta
from typing import Callable, Sequence

from ..models import RunResult
from ..timeutil import isoformat, utcnow
from .service import HotPulseService

logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(
        self,
        service: HotPulseService,
        *,
        stop_event: threading.Event | None = None,
        clock: Callable[[], datetime] = utcnow,
        rng: random.Random | None = None,
    ) -> None:
        self.service = service
        self.stop_event = stop_event or threading.Event()
        self.clock = clock
        self.rng = rng or random.Random()
        self._next_due: dict[str, datetime] = {}
        self._last_result: dict[str, dict[str, object]] = {}

    def _interval(self, platform: str) -> int:
        cfg = self.service.config.platform(platform)
        return max(cfg.interval_seconds, cfg.min_interval_seconds, 5)

    def due_platforms(self, *, now: datetime | None = None, force: bool = False) -> list[str]:
        current = now or self.clock()
        due: list[str] = []
        for name in self.service.platforms:
            if force:
                due.append(name)
                continue
            next_at = self._next_due.get(name)
            if next_at is None or current >= next_at:
                due.append(name)
        return due

    def run_once(self, *, force: bool = False, limit: int | None = None) -> list[RunResult]:
        due = self.due_platforms(force=force)
        if not due:
            return []
        logger.info("Scheduler running platforms: %s", ", ".join(due))
        results = self.service.run(due, limit=limit)
        now = self.clock()
        for name in due:
            delay = self._interval(name)
            if self.service.config.scheduler.jitter_seconds > 0:
                delay += self.rng.uniform(0, self.service.config.scheduler.jitter_seconds)
            self._next_due[name] = now + timedelta(seconds=delay)
        for result in results:
            self._last_result[result.platform] = result.to_dict()
        return results

    def run_forever(
        self,
        *,
        limit: int | None = None,
        once: bool = False,
        max_cycles: int | None = None,
    ) -> list[RunResult]:
        if once:
            return self.run_once(force=True, limit=limit)
        cycles = 0
        last_results: list[RunResult] = []
        while not self.stop_event.is_set():
            due = self.due_platforms()
            if due:
                last_results = self.run_once(limit=limit)
                cycles += 1
                if max_cycles is not None and cycles >= max_cycles:
                    break
                continue
            wait_seconds = self._seconds_until_next()
            self.stop_event.wait(min(max(wait_seconds, 0.2), 5.0))
        return last_results

    def _seconds_until_next(self) -> float:
        now = self.clock()
        next_times = [value for value in self._next_due.values() if value > now]
        if not next_times:
            return 1.0
        return max(0.0, (min(next_times) - now).total_seconds())

    def status(self) -> dict[str, object]:
        return {
            "next_due": {name: isoformat(value) for name, value in sorted(self._next_due.items())},
            "last_result": dict(self._last_result),
        }

    def stop(self) -> None:
        self.stop_event.set()
