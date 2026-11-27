#!/usr/bin/env bash
# 把同级 HotPulse 仓库的运行时复制到博客，供 GitHub Actions 使用。
# 用法：tools/vendor-hotpulse.sh
# 可选：HOTPULSE_SRC=/path/to/hotpulse
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${HOTPULSE_SRC:-${ROOT}/../tools/hotpulse}"
DEST="${ROOT}/tools/hotpulse"

if [[ ! -x "${SRC}/hotpulse" ]]; then
  echo "找不到 HotPulse 仓库：${SRC}" >&2
  echo "请设置 HOTPULSE_SRC，例如：HOTPULSE_SRC=~/tools/hotpulse $0" >&2
  exit 1
fi

rm -rf -- "${DEST}/src" "${DEST}/config"
cp -a "${SRC}/src" "${DEST}/src"
cp -a "${SRC}/config" "${DEST}/config"
cp -a "${SRC}/hotpulse" "${DEST}/hotpulse"
chmod 755 "${DEST}/hotpulse"
echo "已从 ${SRC} 更新运行时副本"
