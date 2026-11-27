"""HotPulse 命令行入口。"""

from __future__ import annotations

import argparse
import json
import shutil
import signal
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Sequence

from . import __version__
from .analysis.keywords import extract_keywords
from .api import create_server
from .config import Config, load_config
from .errors import HotPulseError
from .export import build_export
from .logging_utils import configure_logging
from .models import RunResult
from .probe import run_probe
from .scheduler import HotPulseService, Scheduler
from .storage import Repository


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="hotpulse",
        description="Layered multi-platform hot-topic aggregator (Bilibili, Zhihu, Douyin, Tieba, Reddit, GitHub).",
    )
    parser.add_argument("--config", help="Path to a TOML config file")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument("--log-level", help="Override app.log_level")
    parser.add_argument("--version", action="version", version=f"hotpulse {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Collect all platforms once")
    _common(run, suppress=True)
    run.add_argument("--platform", action="append", help="Only run this platform; repeatable")
    run.add_argument("--limit", type=int, help="Items per platform (clamped by config)")
    run.set_defaults(func=cmd_run)

    serve = sub.add_parser("serve", help="Start the JSON API")
    _common(serve, suppress=True)
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.set_defaults(func=cmd_serve)

    daemon = sub.add_parser("daemon", help="Run the interval scheduler")
    _common(daemon, suppress=True)
    daemon.add_argument("--once", action="store_true", help="Run one forced cycle and exit")
    daemon.add_argument("--cycles", type=int, help="Stop after this many scheduler cycles")
    daemon.add_argument("--limit", type=int)
    daemon.set_defaults(func=cmd_daemon)

    status = sub.add_parser("status", help="Show database and run status")
    _common(status, suppress=True)
    status.set_defaults(func=cmd_status)

    topics = sub.add_parser("topics", help="List the latest scored topics")
    _common(topics, suppress=True)
    topics.add_argument("--platform")
    topics.add_argument("--category")
    topics.add_argument("--q", dest="query")
    topics.add_argument("--min-score", type=float)
    topics.add_argument("--hours", type=float)
    topics.add_argument("--limit", type=int, default=30)
    topics.set_defaults(func=cmd_topics)

    clusters = sub.add_parser("clusters", help="List cross-platform clusters")
    _common(clusters, suppress=True)
    clusters.add_argument("--limit", type=int, default=20)
    clusters.set_defaults(func=cmd_clusters)

    keywords = sub.add_parser("keywords", help="Extract keyword candidates from latest topics")
    _common(keywords, suppress=True)
    keywords.add_argument("--limit", type=int, default=20)
    keywords.set_defaults(func=cmd_keywords)

    runs = sub.add_parser("runs", help="List collection runs")
    _common(runs, suppress=True)
    runs.add_argument("--platform")
    runs.add_argument("--limit", type=int, default=20)
    runs.set_defaults(func=cmd_runs)

    probe = sub.add_parser("probe", help="Probe live platform endpoints without writing the database")
    _common(probe, suppress=True)
    probe.add_argument("--platform", action="append")
    probe.add_argument("--limit", type=int, default=3)
    probe.add_argument("--output", help="Write the full probe report to this JSON file")
    probe.set_defaults(func=cmd_probe)

    export = sub.add_parser("export", help="Export a stable JSON snapshot for a website or dashboard")
    _common(export, suppress=True)
    export.add_argument("--platform", help="Only export this platform")
    export.add_argument("--limit", type=int, default=100, help="Maximum topics (1..500)")
    export.add_argument("--output", help="Write JSON to this file instead of stdout")
    export.set_defaults(func=cmd_export)

    return parser


def _common(parser: argparse.ArgumentParser, *, suppress: bool = False) -> None:
    kwargs: dict[str, Any] = {"default": argparse.SUPPRESS} if suppress else {}
    parser.add_argument("--config", help="Path to a TOML config file", **kwargs)
    parser.add_argument("--json", action="store_true", help="Emit JSON", **kwargs)
    parser.add_argument("--log-level", help="Override app.log_level", **kwargs)


def _config(args: argparse.Namespace) -> Config:
    config = load_config(getattr(args, "config", None))
    override = getattr(args, "log_level", None)
    if override:
        config.app.log_level = override.upper()
    configure_logging(config.app.log_level)
    return config


def _wants_json(args: argparse.Namespace) -> bool:
    return bool(getattr(args, "json", False))


def cmd_run(args: argparse.Namespace, config: Config) -> int:
    platforms = _flatten_platforms(getattr(args, "platform", None))
    service = HotPulseService(config)
    try:
        runs = service.run(platforms, limit=args.limit)
    finally:
        service.close()
    if _wants_json(args):
        print(json.dumps([run.to_dict() for run in runs], ensure_ascii=False, indent=2))
    else:
        _print_runs(runs)
    if runs and all(run.status == "failed" for run in runs):
        return 1
    return 0


def cmd_serve(args: argparse.Namespace, config: Config) -> int:
    service = HotPulseService(config)
    server = create_server(service, host=args.host, port=args.port)
    host, port = server.server_address[:2]
    print(f"HotPulse API listening on http://{host}:{port}", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping API.", flush=True)
    finally:
        server.server_close()
        service.close()
    return 0


def cmd_daemon(args: argparse.Namespace, config: Config) -> int:
    if args.cycles is not None and args.cycles < 1:
        print("error: --cycles must be >= 1", file=sys.stderr)
        return 2
    service = HotPulseService(config)
    scheduler = Scheduler(service)

    def _stop(signum: int, frame: object) -> None:
        print(f"\nReceived signal {signum}; stopping scheduler.", flush=True)
        scheduler.stop()

    for signum in (signal.SIGTERM, signal.SIGINT):
        try:
            signal.signal(signum, _stop)
        except (ValueError, OSError):
            pass
    try:
        if args.once:
            runs = scheduler.run_once(force=True, limit=args.limit)
        else:
            print(
                f"Scheduler started for {', '.join(service.platforms)}; "
                "intervals come from the platform config.",
                flush=True,
            )
            runs = scheduler.run_forever(limit=args.limit, max_cycles=args.cycles)
    except KeyboardInterrupt:
        scheduler.stop()
        runs = []
    finally:
        service.close()
    if _wants_json(args):
        print(json.dumps([run.to_dict() for run in runs], ensure_ascii=False, indent=2))
    elif runs:
        _print_runs(runs)
    if runs and all(run.status == "failed" for run in runs):
        return 1
    return 0


def cmd_status(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        summary = repo.summary()
    finally:
        repo.close()
    if _wants_json(args):
        print(json.dumps({"config": config.public_dict(), "database": summary}, ensure_ascii=False, indent=2))
        return 0
    print(f"Database: {summary['database']} ({summary['database_size_bytes']} bytes)")
    print(f"Topics: {summary['topics']}  Snapshots: {summary['snapshots']}  Runs: {summary['runs']}")
    if not summary["platforms"]:
        print("\nNo data yet. Run `hotpulse run` first.")
    else:
        print("\nPlatform             Topics  Last seen")
        print("-" * 62)
        for item in summary["platforms"]:
            print(f"{item['platform']:<20} {item['topics']:>6}  {item['last_seen'] or '-'}")
    if summary["latest_runs"]:
        print("\nLatest runs:")
        _print_runs(
            [
                RunResult(
                    platform=row["platform"],
                    status=row["status"],
                    item_count=int(row["item_count"]),
                    duration_ms=int(row["duration_ms"]),
                    run_id=row["id"],
                    source=row["source"],
                    error=row["error"],
                )
                for row in summary["latest_runs"]
            ]
        )
    print(f"\nConfig: {config.source_path or '(built-in defaults)'}")
    return 0


def cmd_topics(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        rows = repo.latest_items(
            platform=args.platform,
            category=args.category,
            query=args.query,
            min_score=args.min_score,
            max_age_hours=args.hours,
            limit=args.limit,
        )
    finally:
        repo.close()
    if _wants_json(args):
        print(json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No topics matched. Run `hotpulse run` or relax the filters.")
        return 0
    _print_topics(rows)
    return 0


def cmd_clusters(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        rows = repo.latest_clusters(limit=args.limit)
    finally:
        repo.close()
    if _wants_json(args):
        print(json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No cross-platform clusters yet. They appear when two platforms cover the same topic.")
        return 0
    for index, cluster in enumerate(rows, start=1):
        print(f"{index:>2}. [{cluster['score']:>5.1f}] {cluster['title']}")
        for member in cluster["members"]:
            print(f"    - {member['platform']:<10} {member['title'][:70]}")
        print()
    return 0


def cmd_keywords(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        rows = repo.latest_items(limit=500)
    finally:
        repo.close()
    keywords = extract_keywords(
        [SimpleNamespace(platform=row["platform"], title=row["title"]) for row in rows],
        args.limit,
    )
    if _wants_json(args):
        print(json.dumps([keyword.to_dict() for keyword in keywords], ensure_ascii=False, indent=2))
        return 0
    if not keywords:
        print("Not enough repeated titles yet to extract keywords.")
        return 0
    for index, keyword in enumerate(keywords, start=1):
        platforms = ", ".join(keyword.platforms)
        print(f"{index:>2}. {keyword.term:<20} count={keyword.count:<3} score={keyword.score:>5.2f}  [{platforms}]")
    return 0


def cmd_runs(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        rows = repo.runs(platform=args.platform, limit=args.limit)
    finally:
        repo.close()
    if _wants_json(args):
        print(json.dumps({"count": len(rows), "items": rows}, ensure_ascii=False, indent=2))
        return 0
    if not rows:
        print("No runs yet.")
        return 0
    print(f"{'ID':>5}  {'PLATFORM':<10} {'STATUS':<9} {'ITEMS':>5} {'MS':>7}  STARTED")
    print("-" * 70)
    for row in rows:
        print(
            f"{row['id']:>5}  {row['platform']:<10} {row['status']:<9} "
            f"{row['item_count']:>5} {row['duration_ms']:>7}  {row['started_at']}"
        )
    return 0


def cmd_probe(args: argparse.Namespace, config: Config) -> int:
    platforms = _flatten_platforms(getattr(args, "platform", None))
    report = run_probe(config, platforms, limit=args.limit)
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if _wants_json(args):
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f"Probe at {report['generated_at']}  (limit={report['limit']})")
        print(f"{'PLATFORM':<12} {'STATUS':<17} {'ITEMS':>5} {'MS':>7}  SOURCE / ERROR")
        print("-" * 100)
        for item in report["platforms"]:
            detail = item.get("source") or item.get("error", "")
            print(
                f"{item['platform']:<12} {item['status']:<17} {item['item_count']:>5} "
                f"{item['latency_ms']:>7}  {str(detail)[:60]}"
            )
        if args.output:
            print(f"\nFull report: {output}")
    return 0 if report["summary"].get("success", 0) > 0 else 1


def cmd_export(args: argparse.Namespace, config: Config) -> int:
    repo = Repository(config.app.database)
    try:
        payload = build_export(
            config,
            repo,
            limit=args.limit,
            platform=args.platform,
        )
    finally:
        repo.close()
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output).expanduser()
        output.parent.mkdir(parents=True, exist_ok=True)
        try:
            output.write_text(text, encoding="utf-8")
        except OSError as exc:
            print(f"error: could not write export: {exc}", file=sys.stderr)
            return 2
        if _wants_json(args):
            print(
                json.dumps(
                    {
                        "output": str(output),
                        "topics": payload["stats"]["topics"],
                        "generated_at": payload["generated_at"],
                    },
                    ensure_ascii=False,
                )
            )
        else:
            print(f"Exported {payload['stats']['topics']} topics to {output}")
        return 0
    print(text, end="")
    return 0


def _flatten_platforms(values: Sequence[str] | None) -> list[str] | None:
    if not values:
        return None
    flattened: list[str] = []
    for value in values:
        flattened.extend(part.strip() for part in value.split(",") if part.strip())
    return list(dict.fromkeys(flattened)) or None


def _print_runs(runs: Sequence[RunResult]) -> None:
    if not runs:
        print("No platforms were run.")
        return
    print(f"{'PLATFORM':<12} {'STATUS':<9} {'ITEMS':>5} {'DROP':>5} {'MS':>7}  SOURCE / ERROR")
    print("-" * 104)
    for run in runs:
        detail = run.source or (run.error or "")
        print(
            f"{run.platform:<12} {run.status:<9} {run.item_count:>5} {run.dropped:>5} "
            f"{run.duration_ms:>7}  {str(detail).replace(chr(10), ' ')[:62]}"
        )


def _print_topics(rows: Sequence[dict[str, Any]]) -> None:
    width = max(40, shutil.get_terminal_size((120, 24)).columns)
    title_width = max(20, width - 66)
    print(f"{'#':>3} {'PLATFORM':<10} {'SCORE':>6} {'TREND':<8} {'CATEGORY':<14} TITLE")
    print("-" * width)
    for index, row in enumerate(rows, start=1):
        rank = row.get("rank") or index
        score = float(row.get("score") or 0)
        trend = str(row.get("trend") or "-")
        category = str(row.get("category") or "-")
        title = str(row.get("title") or "").replace("\n", " ")[:title_width]
        print(f"{int(rank):>3} {row['platform']:<10} {score:>6.1f} {trend:<8} {category:<14} {title}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = _config(args)
        return int(args.func(args, config) or 0)
    except HotPulseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
