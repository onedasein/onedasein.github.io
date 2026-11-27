"""SQLite 存储层。

设计要点：
- 每个线程使用独立连接（:memory: 例外，用锁串行化）；
- runs 记录每次采集，snapshots 追加保存排名/热度/分数，topics 保存主题最新元数据；
- 所有写入一个 run 在一个事务里完成，避免“有 run 无数据”的中间态。
"""

from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Iterator, Sequence

from ..errors import StorageError
from ..models import Cluster, PreviousSnapshot, RunResult, ScoredItem
from ..timeutil import isoformat, utcnow
from .schema import SCHEMA_SQL, SCHEMA_VERSION


class Repository:
    def __init__(self, database: str, *, timeout: float = 10.0, initialize: bool = True) -> None:
        self.database = database
        self.timeout = timeout
        self._memory_conn: sqlite3.Connection | None = None
        self._lock = threading.RLock()
        if database == ":memory:":
            self._memory_conn = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
            self._configure(self._memory_conn)
        else:
            path = Path(database).expanduser()
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise StorageError(
                    f"Could not create database directory: {path.parent}",
                    remediation="Check write permissions or set app.database to a writable path.",
                ) from exc
            self.database = str(path)
        if initialize:
            self.initialize_schema()

    def _configure(self, connection: sqlite3.Connection) -> None:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA synchronous=NORMAL")
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(f"PRAGMA busy_timeout={int(self.timeout * 1000)}")

    def _open(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=self.timeout, isolation_level=None)
        self._configure(connection)
        return connection

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        if self._memory_conn is not None:
            with self._lock:
                yield self._memory_conn
            return
        connection = self._open()
        try:
            yield connection
        finally:
            connection.close()

    def initialize_schema(self) -> None:
        try:
            with self.connection() as conn:
                conn.executescript(SCHEMA_SQL)
                conn.execute(
                    "INSERT INTO schema_meta(key, value) VALUES('version', ?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                    (str(SCHEMA_VERSION),),
                )
                conn.commit()
        except sqlite3.Error as exc:
            raise StorageError(
                f"Could not initialize SQLite schema: {exc}",
                remediation="Check the database path, disk space, and file permissions.",
            ) from exc

    def close(self) -> None:
        if self._memory_conn is not None:
            with self._lock:
                self._memory_conn.close()
                self._memory_conn = None

    # ------------------------------------------------------------------ writes
    def save_run(
        self,
        result: RunResult,
        items: Sequence[ScoredItem],
        *,
        started_at: datetime,
        finished_at: datetime,
    ) -> int:
        """原子写入一次 run 及其快照；返回 run id。"""
        item_count = len(items)
        result.item_count = item_count
        with self.connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                cursor = conn.execute(
                    "INSERT INTO runs(platform, started_at, finished_at, status, item_count, duration_ms, source, error) "
                    "VALUES(?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        result.platform,
                        isoformat(started_at),
                        isoformat(finished_at),
                        result.status,
                        item_count,
                        max(0, int(result.duration_ms)),
                        result.source,
                        result.error,
                    ),
                )
                run_id = int(cursor.lastrowid or 0)
                for item in items:
                    metadata = _json_dumps(item.metadata)
                    observed = isoformat(item.observed_at) or isoformat(finished_at)
                    published = isoformat(item.published_at)
                    conn.execute(
                        "INSERT INTO snapshots("
                        "platform, external_id, run_id, observed_at, rank, hot_value, score, trend, category, "
                        "title, url, fingerprint, metadata) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            item.platform,
                            item.external_id,
                            run_id,
                            observed,
                            item.rank,
                            item.hot_value,
                            item.score,
                            item.trend,
                            item.category,
                            item.title,
                            item.url,
                            item.fingerprint,
                            metadata,
                        ),
                    )
                    conn.execute(
                        "INSERT INTO topics("
                        "platform, external_id, first_seen_at, last_seen_at, title, url, author, summary, "
                        "category, published_at, fingerprint) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                        "ON CONFLICT(platform, external_id) DO UPDATE SET "
                        "last_seen_at=excluded.last_seen_at, title=excluded.title, url=excluded.url, "
                        "author=COALESCE(excluded.author, topics.author), "
                        "summary=COALESCE(excluded.summary, topics.summary), "
                        "category=excluded.category, "
                        "published_at=COALESCE(excluded.published_at, topics.published_at), "
                        "fingerprint=excluded.fingerprint",
                        (
                            item.platform,
                            item.external_id,
                            observed,
                            observed,
                            item.title,
                            item.url,
                            item.author,
                            item.summary,
                            item.category,
                            published,
                            item.fingerprint,
                        ),
                    )
                conn.commit()
                return run_id
            except sqlite3.Error as exc:
                conn.rollback()
                raise StorageError(
                    f"Could not save run for {result.platform}: {exc}",
                    remediation="Check SQLite permissions and disk space; the run was not committed.",
                ) from exc

    def save_failed_run(
        self,
        result: RunResult,
        *,
        started_at: datetime,
        finished_at: datetime,
    ) -> int:
        return self.save_run(result, [], started_at=started_at, finished_at=finished_at)

    def replace_clusters(self, clusters: Sequence[Cluster]) -> None:
        with self.connection() as conn:
            try:
                conn.execute("BEGIN IMMEDIATE")
                conn.execute("DELETE FROM cluster_members")
                conn.execute("DELETE FROM clusters")
                for cluster in clusters:
                    conn.execute(
                        "INSERT INTO clusters(id, title, score, item_count, updated_at) VALUES(?, ?, ?, ?, ?)",
                        (
                            cluster.cluster_id,
                            cluster.title,
                            cluster.score,
                            cluster.item_count,
                            isoformat(cluster.updated_at),
                        ),
                    )
                    conn.executemany(
                        "INSERT INTO cluster_members(cluster_id, platform, external_id, title, url, score) "
                        "VALUES(?, ?, ?, ?, ?, ?)",
                        [
                            (cluster.cluster_id, member.platform, member.external_id, member.title, member.url, member.score)
                            for member in cluster.members
                        ],
                    )
                conn.commit()
            except sqlite3.Error as exc:
                conn.rollback()
                raise StorageError(
                    f"Could not save clusters: {exc}",
                    remediation="Check SQLite permissions and disk space.",
                ) from exc

    # ------------------------------------------------------------------- reads
    def previous_map(self, platform: str) -> dict[str, PreviousSnapshot]:
        try:
            with self.connection() as conn:
                rows = conn.execute(
                    "SELECT s.external_id, s.rank, s.hot_value, s.score, s.observed_at "
                    "FROM snapshots s "
                    "JOIN (SELECT external_id, MAX(id) AS max_id FROM snapshots WHERE platform=? GROUP BY external_id) latest "
                    "ON s.id = latest.max_id",
                    (platform,),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read previous snapshots: {exc}") from exc
        return {
            str(row["external_id"]): PreviousSnapshot(
                rank=int(row["rank"]),
                hot_value=row["hot_value"],
                score=row["score"],
                observed_at=row["observed_at"],
            )
            for row in rows
        }

    def latest_items(
        self,
        *,
        platform: str | None = None,
        category: str | None = None,
        query: str | None = None,
        min_score: float | None = None,
        max_age_hours: float | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        params: list[Any] = []
        cte = (
            "WITH latest AS (SELECT s.*, ROW_NUMBER() OVER "
            "(PARTITION BY s.platform, s.external_id ORDER BY s.id DESC) AS rn FROM snapshots s"
        )
        if platform:
            cte += " WHERE s.platform = ?"
            params.append(platform)
        cte += ")"
        conditions = ["rn = 1"]
        if category:
            conditions.append("category = ?")
            params.append(category)
        if query:
            # snapshots 只保存展示所需的标题/URL；摘要属于 topics 表，MVP 的搜索只匹配标题。
            conditions.append("title LIKE ?")
            params.append(f"%{query}%")
        if min_score is not None:
            conditions.append("score >= ?")
            params.append(float(min_score))
        if max_age_hours is not None and max_age_hours > 0:
            conditions.append("observed_at >= ?")
            params.append(isoformat(utcnow() - timedelta(hours=max_age_hours)))
        sql = (
            cte
            + " SELECT * FROM latest WHERE "
            + " AND ".join(conditions)
            + " ORDER BY score DESC, platform ASC, rank ASC LIMIT ?"
        )
        params.append(limit)
        try:
            with self.connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read latest items: {exc}") from exc
        return [_snapshot_row(row) for row in rows]

    def history(self, platform: str, external_id: str, *, limit: int = 50) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 500))
        try:
            with self.connection() as conn:
                rows = conn.execute(
                    "SELECT * FROM snapshots WHERE platform=? AND external_id=? ORDER BY id DESC LIMIT ?",
                    (platform, external_id, limit),
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read history: {exc}") from exc
        return [_snapshot_row(row) for row in rows]

    def runs(self, *, platform: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 200))
        sql = "SELECT * FROM runs"
        params: list[Any] = []
        if platform:
            sql += " WHERE platform=?"
            params.append(platform)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        try:
            with self.connection() as conn:
                rows = conn.execute(sql, params).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read runs: {exc}") from exc
        return [dict(row) for row in rows]

    def latest_clusters(self, *, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, min(int(limit), 100))
        try:
            with self.connection() as conn:
                rows = conn.execute(
                    "SELECT c.id, c.title, c.score, c.item_count, c.updated_at, "
                    "m.platform, m.external_id, m.title AS member_title, m.url, m.score AS member_score "
                    "FROM clusters c LEFT JOIN cluster_members m ON c.id = m.cluster_id "
                    "ORDER BY c.score DESC, c.id ASC"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read clusters: {exc}") from exc
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            cluster_id = str(row["id"])
            entry = grouped.setdefault(
                cluster_id,
                {
                    "cluster_id": cluster_id,
                    "title": row["title"],
                    "score": row["score"],
                    "item_count": row["item_count"],
                    "updated_at": row["updated_at"],
                    "members": [],
                },
            )
            if row["platform"]:
                entry["members"].append(
                    {
                        "platform": row["platform"],
                        "external_id": row["external_id"],
                        "title": row["member_title"],
                        "url": row["url"],
                        "score": row["member_score"],
                    }
                )
        return list(grouped.values())[:limit]

    def summary(self) -> dict[str, Any]:
        try:
            with self.connection() as conn:
                topic_count = int(conn.execute("SELECT COUNT(*) FROM topics").fetchone()[0])
                snapshot_count = int(conn.execute("SELECT COUNT(*) FROM snapshots").fetchone()[0])
                run_count = int(conn.execute("SELECT COUNT(*) FROM runs").fetchone()[0])
                latest_runs = conn.execute(
                    "SELECT r.* FROM runs r WHERE r.id IN (SELECT MAX(id) FROM runs GROUP BY platform) ORDER BY platform"
                ).fetchall()
                platforms = conn.execute(
                    "SELECT platform, COUNT(*) AS topics, MAX(last_seen_at) AS last_seen "
                    "FROM topics GROUP BY platform ORDER BY platform"
                ).fetchall()
        except sqlite3.Error as exc:
            raise StorageError(f"Could not read summary: {exc}") from exc
        try:
            size = Path(self.database).stat().st_size if self.database != ":memory:" else 0
        except OSError:
            size = 0
        return {
            "database": self.database,
            "database_size_bytes": size,
            "topics": topic_count,
            "snapshots": snapshot_count,
            "runs": run_count,
            "platforms": [
                {
                    "platform": row["platform"],
                    "topics": row["topics"],
                    "last_seen": row["last_seen"],
                }
                for row in platforms
            ],
            "latest_runs": [dict(row) for row in latest_runs],
        }


def _json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return "{}"


def _snapshot_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data.pop("rn", None)  # latest_items 的窗口函数内部列，不暴露给 API/CLI
    metadata = data.get("metadata")
    if isinstance(metadata, str):
        try:
            data["metadata"] = json.loads(metadata)
        except json.JSONDecodeError:
            data["metadata"] = {}
    else:
        data["metadata"] = {}
    return data
