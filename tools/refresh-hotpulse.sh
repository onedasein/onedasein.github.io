#!/usr/bin/env bash
# 采集并导出 HotPulse 快照，校验后原子替换 assets/data/hotpulse.json。
# 用法：tools/refresh-hotpulse.sh
# 可选：HOTPULSE_BIN、HOTPULSE_DB、HOTPULSE_OUT、HOTPULSE_LIMIT、
#       HOTPULSE_EXPORT_LIMIT、HOTPULSE_MIN_TOPICS、HOTPULSE_MIN_PLATFORMS、
#       HOTPULSE_MAX_AGE_HOURS
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${HOTPULSE_OUT:-${ROOT}/assets/data/hotpulse.json}"
LIMIT="${HOTPULSE_LIMIT:-20}"
EXPORT_LIMIT="${HOTPULSE_EXPORT_LIMIT:-200}"
MIN_TOPICS="${HOTPULSE_MIN_TOPICS:-20}"
MIN_PLATFORMS="${HOTPULSE_MIN_PLATFORMS:-3}"
MAX_AGE_HOURS="${HOTPULSE_MAX_AGE_HOURS:-6}"

BIN="${HOTPULSE_BIN:-}"
if [[ -z "${BIN}" ]]; then
  if [[ -x "${ROOT}/../tools/hotpulse/hotpulse" ]]; then
    BIN="${ROOT}/../tools/hotpulse/hotpulse"
  elif [[ -x "${ROOT}/tools/hotpulse/hotpulse" ]]; then
    BIN="${ROOT}/tools/hotpulse/hotpulse"
  fi
fi

if [[ ! -x "${BIN}" ]]; then
  echo "找不到可执行的 HotPulse：${BIN:-<未设置>}" >&2
  echo "请设置 HOTPULSE_BIN，例如：HOTPULSE_BIN=~/tools/hotpulse/hotpulse $0" >&2
  exit 1
fi

mkdir -p "$(dirname -- "${OUT}")"
TMP="$(mktemp "${OUT}.tmp.XXXXXX")"
trap 'rm -f -- "${TMP}"' EXIT

echo "采集：limit=${LIMIT}，数据库=${HOTPULSE_DB:-HotPulse 默认}"

# run 在任一平台失败时返回 1（例如未配置 Reddit 凭据），仍继续导出其余平台。
set +e
"${BIN}" run --limit "${LIMIT}"
RUN_STATUS=$?
set -e
if (( RUN_STATUS > 1 )); then
  echo "HotPulse 采集失败（退出码 ${RUN_STATUS}）" >&2
  exit "${RUN_STATUS}"
fi
if (( RUN_STATUS == 1 )); then
  echo "部分平台采集失败，继续校验已获取的数据" >&2
fi

"${BIN}" export --limit "${EXPORT_LIMIT}" --output "${TMP}"

python3 - "${TMP}" "${OUT}" "${MIN_TOPICS}" "${MIN_PLATFORMS}" "${MAX_AGE_HOURS}" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

tmp, out, min_topics, min_platforms, max_age_hours = sys.argv[1:]
min_topics = max(1, int(min_topics))
min_platforms = max(1, int(min_platforms))
max_age_hours = max(1, int(max_age_hours))

with open(tmp, encoding="utf-8") as fh:
    data = json.load(fh)

if data.get("schema_version") != 1:
    raise SystemExit(f"快照 schema_version 不是 1：{data.get('schema_version')!r}")

stats = data.get("stats") or {}
topics = data.get("topics") or []
active = int(stats.get("active_platforms") or 0)
if len(topics) < min_topics:
    raise SystemExit(f"快照只有 {len(topics)} 条热点，低于阈值 {min_topics}，保留旧快照")
if active < min_platforms:
    raise SystemExit(f"只有 {active} 个平台有数据，低于阈值 {min_platforms}，保留旧快照")

through = data.get("data_through")
try:
    through_at = datetime.fromisoformat(str(through).replace("Z", "+00:00"))
except ValueError:
    raise SystemExit(f"data_through 不是有效时间：{through!r}")
age_hours = (datetime.now(timezone.utc) - through_at).total_seconds() / 3600
if age_hours > max_age_hours:
    raise SystemExit(f"快照已过期（{age_hours:.1f} 小时），超过阈值 {max_age_hours} 小时，保留旧快照")

os.chmod(tmp, 0o644)
os.replace(tmp, out)
print(f"已更新 {out}：{len(topics)} 条热点，{active} 个平台，截至 {data.get('data_through')}")
PY
