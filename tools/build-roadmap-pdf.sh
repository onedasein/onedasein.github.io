#!/usr/bin/env bash
#
# 把 _typst/roadmap/ 里的 Typst 源码编译成站点上可下载的 PDF。
#
#   bash tools/build-roadmap-pdf.sh
#
# 依赖 typst（>= 0.13）。优先用 PATH 里的 typst，也可用 TYPST=/path/to/typst 指定。
set -euo pipefail

cd "$(dirname "$0")/.."

TYPST="${TYPST:-$(command -v typst || true)}"
if [ -z "$TYPST" ]; then
  for c in "$HOME/typst-x86_64-unknown-linux-musl/typst" /usr/local/bin/typst; do
    if [ -x "$c" ]; then TYPST="$c"; break; fi
  done
fi
[ -n "$TYPST" ] || { echo "找不到 typst，请设置 TYPST=/path/to/typst" >&2; exit 1; }

SRC="_typst/roadmap"
OUT="assets/roadmap/cs-roadmap.pdf"
mkdir -p "$(dirname "$OUT")"

echo ">>> $("$TYPST" --version)"
"$TYPST" compile "$SRC/main.typ" "$OUT"
echo "✅ 生成 $OUT（$(du -h "$OUT" | cut -f1)）"
