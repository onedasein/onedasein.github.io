"""调度层编排器：采集 → 清洗 → 分析 → 存储。"""

from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime
from typing import Sequence

from ..analysis import AnalysisEngine, AnalysisResult
from ..cleaner import Cleaner, CleanReport
from ..collectors import BaseCollector, CollectionResult, create_configured_collectors
from ..config import Config
from ..errors import HotPulseError, StorageError
from ..models import CleanItem, CollectedItem, PreviousSnapshot, RunResult, ScoredItem
from ..storage import Repository
from ..timeutil import utcnow

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Outcome:
    platform: str
    started_at: datetime
    finished_at: datetime
    previous: dict[str, PreviousSnapshot] = field(default_factory=dict)
    collection: CollectionResult | None = None
    clean: CleanReport | None = None
    error: str | None = None

    @property
    def clean_items(self) -> list[CleanItem]:
        return self.clean.items if self.clean else []

    @property
    def source(self) -> str | None:
        return self.collection.source if self.collection else None


class HotPulseService:
    def __init__(
        self,
        config: Config,
        *,
        repository: Repository | None = None,
        collectors: dict[str, BaseCollector] | None = None,
        cleaner: Cleaner | None = None,
        analyzer: AnalysisEngine | None = None,
    ) -> None:
        self.config = config
        self.repo = repository or Repository(config.app.database)
        self.collectors = collectors if collectors is not None else create_configured_collectors(config)
        self.cleaner = cleaner or Cleaner(config.cleaner)
        self.analyzer = analyzer or AnalysisEngine(config.analysis, config.platform_weights())
        self._run_lock = threading.RLock()

    @property
    def platforms(self) -> list[str]:
        return list(self.collectors)

    def close(self) -> None:
        for collector in self.collectors.values():
            try:
                collector.http.close()
            except Exception:  # pragma: no cover - 关闭失败不应阻碍退出
                pass
        self.repo.close()

    def _collect_one(self, name: str, limit: int | None) -> _Outcome:
        started = utcnow()
        previous: dict[str, PreviousSnapshot] = {}
        try:
            previous = self.repo.previous_map(name)
            collection = self.collectors[name].collect(limit)
            clean = self.cleaner.clean(collection.items)
            finished = utcnow()
            return _Outcome(
                platform=name,
                started_at=started,
                finished_at=finished,
                previous=previous,
                collection=collection,
                clean=clean,
            )
        except HotPulseError as exc:
            logger.warning("Platform %s failed: %s", name, exc)
            return _Outcome(
                platform=name,
                started_at=started,
                finished_at=utcnow(),
                previous=previous,
                error=str(exc),
            )
        except Exception as exc:  # 适配器 bug 不能拖垮整个调度轮次
            logger.exception("Platform %s crashed", name)
            return _Outcome(
                platform=name,
                started_at=started,
                finished_at=utcnow(),
                previous=previous,
                error=f"{type(exc).__name__}: {exc}",
            )

    def _selected(self, platforms: Sequence[str] | None) -> list[str]:
        if platforms is None:
            return list(self.collectors)
        selected: list[str] = []
        for name in platforms:
            if name not in self.collectors:
                raise HotPulseError(
                    f"Platform is not enabled or unknown: {name}",
                    remediation=f"Enabled platforms: {', '.join(self.collectors) or '(none)'}",
                )
            if name not in selected:
                selected.append(name)
        return selected

    def run(self, platforms: Sequence[str] | None = None, *, limit: int | None = None) -> list[RunResult]:
        """执行一轮采集，返回每个平台的结果；单个平台失败不影响其他平台。"""
        selected = self._selected(platforms)
        if not selected:
            return []
        with self._run_lock:
            workers = max(1, min(self.config.scheduler.max_workers, len(selected)))
            with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hotpulse") as pool:
                outcomes = list(pool.map(lambda name: self._collect_one(name, limit), selected))

            analysis_error: str | None = None
            analysis: AnalysisResult | None = None
            clean_items = [item for outcome in outcomes for item in outcome.clean_items]
            if clean_items:
                previous = {outcome.platform: outcome.previous for outcome in outcomes}
                try:
                    analysis = self.analyzer.analyze(
                        clean_items,
                        previous,
                        platform_weights=self.config.platform_weights(),
                    )
                except Exception as exc:  # 分析层异常时仍保留失败记录
                    logger.exception("Analysis failed")
                    analysis_error = f"{type(exc).__name__}: {exc}"

            scored_by_platform: dict[str, list[ScoredItem]] = {}
            if analysis is not None:
                for item in analysis.items:
                    scored_by_platform.setdefault(item.platform, []).append(item)

            runs: list[RunResult] = []
            for outcome in outcomes:
                if outcome.error:
                    result = RunResult(
                        platform=outcome.platform,
                        status="failed",
                        duration_ms=_duration_ms(outcome.started_at, outcome.finished_at),
                        error=outcome.error[:2000],
                    )
                elif analysis_error:
                    result = RunResult(
                        platform=outcome.platform,
                        status="failed",
                        duration_ms=_duration_ms(outcome.started_at, outcome.finished_at),
                        source=outcome.source,
                        error=f"analysis failed: {analysis_error}"[:2000],
                        dropped=outcome.clean.dropped_count if outcome.clean else 0,
                    )
                elif not outcome.clean_items:
                    result = RunResult(
                        platform=outcome.platform,
                        status="empty",
                        duration_ms=_duration_ms(outcome.started_at, outcome.finished_at),
                        source=outcome.source,
                        dropped=outcome.clean.dropped_count if outcome.clean else 0,
                    )
                else:
                    result = RunResult(
                        platform=outcome.platform,
                        status="success",
                        duration_ms=_duration_ms(outcome.started_at, outcome.finished_at),
                        source=outcome.source,
                        dropped=outcome.clean.dropped_count if outcome.clean else 0,
                    )

                items = scored_by_platform.get(outcome.platform, [])
                if result.status == "success" and not items:
                    result.status = "failed"
                    result.error = "analysis produced no scored items"
                try:
                    result.run_id = self.repo.save_run(
                        result,
                        items if result.status == "success" else [],
                        started_at=outcome.started_at,
                        finished_at=outcome.finished_at,
                    )
                except StorageError as exc:
                    logger.error("Could not persist %s run: %s", outcome.platform, exc)
                    result.status = "failed"
                    result.error = str(exc)
                    try:
                        result.run_id = self.repo.save_failed_run(
                            result,
                            started_at=outcome.started_at,
                            finished_at=outcome.finished_at,
                        )
                    except StorageError:
                        # 数据库本身不可用时只能返回内存中的失败结果。
                        logger.exception("Could not persist failure record for %s", outcome.platform)
                runs.append(result)

            if analysis is not None:
                try:
                    self.repo.replace_clusters(analysis.clusters)
                except StorageError as exc:
                    logger.error("Could not persist clusters: %s", exc)
            return runs

    def run_all(self, *, limit: int | None = None) -> list[RunResult]:
        return self.run(limit=limit)

    def preview(
        self,
        platforms: Sequence[str] | None = None,
        *,
        limit: int | None = None,
    ) -> tuple[list[_Outcome], AnalysisResult | None]:
        """只采集/清洗/分析，不落库；供 probe 或调试使用。"""
        selected = self._selected(platforms)
        with ThreadPoolExecutor(max_workers=max(1, min(self.config.scheduler.max_workers, len(selected)))) as pool:
            outcomes = list(pool.map(lambda name: self._collect_one(name, limit), selected))
        clean_items = [item for outcome in outcomes for item in outcome.clean_items]
        analysis = None
        if clean_items:
            previous = {outcome.platform: outcome.previous for outcome in outcomes}
            analysis = self.analyzer.analyze(
                clean_items,
                previous,
                platform_weights=self.config.platform_weights(),
            )
        return outcomes, analysis


def _duration_ms(started: datetime, finished: datetime) -> int:
    return max(0, int((finished - started).total_seconds() * 1000))
