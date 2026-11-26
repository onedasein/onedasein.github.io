#!/usr/bin/env bash
# 把 HotPulse 的最新快照同步到博客的静态数据目录。
# 用法：tools/sync-hotpulse.sh
# 可选：HOTPULSE_BIN=/path/to/hotpulse HOTPULSE_LIMIT=200
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT}/assets/data/hotpulse.json"
BIN="${HOTPULSE_BIN:-${ROOT}/../tools/hotpulse/hotpulse}"
LIMIT="${HOTPULSE_LIMIT:-200}"

if [[ ! -x "${BIN}" ]]; then
  echo "找不到可执行的 HotPulse：${BIN}" >&2
  echo "请设置 HOTPULSE_BIN，例如：HOTPULSE_BIN=~/tools/hotpulse/hotpulse $0" >&2
  exit 1
fi

mkdir -p "$(dirname -- "${OUT}")"
"${BIN}" export --limit "${LIMIT}" --output "${OUT}"
echo "已同步到 ${OUT}"
