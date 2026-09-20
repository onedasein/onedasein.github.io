#!/usr/bin/env bash
#
# 由 _typst/roadmap/ 的 Typst 源同时生成两样东西（一套源 → 网页 + PDF）：
#
#   ① 站点 PDF     assets/roadmap/cs-roadmap.pdf
#   ② 网页版页面   _tabs/roadmap.html 与 roadmap/*.html
#                  （Jekyll 页面：front matter + Typst 导出的 HTML 正文）
#
# 用法： bash tools/build-roadmap.sh
# 依赖： typst >= 0.13（HTML 导出需要 --features html）、python3
#
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
BUILD="$SRC/.build"
mkdir -p "$BUILD" assets/roadmap assets/css
echo ">>> $("$TYPST" --version)"

# Typst 的 HTML 导出每次都会刷这段实验性警告；过滤掉它，但真实报错照旧抛出
run_typst() {
  local log="$BUILD/typst.log"
  if ! "$@" >"$log" 2>&1; then cat "$log" >&2; return 1; fi
  grep -vE 'under active development|behaviour may change|do not rely on|issues/5512' "$log" >&2 || true
}

# ---------------------------------------------------------------- ① PDF
run_typst "$TYPST" compile "$SRC/main.typ" assets/roadmap/cs-roadmap.pdf
echo "✅ assets/roadmap/cs-roadmap.pdf（$(du -h assets/roadmap/cs-roadmap.pdf | cut -f1)）"

# ---------------------------------------------------------------- ② 网页版
page() { # page <章节 .typ> <输出路径> <permalink> <页面标题> [额外 front matter 行]
  local typ="$1" out="$2" perm="$3" title="$4" extra="${5:-}"
  local wrapper="$BUILD/w-$typ"

  printf '#import "../lib.typ": *\n#show: roadmap-web\n#include "../%s"\n' "$typ" >"$wrapper"
  run_typst "$TYPST" compile --features html --format html --pretty \
    --input target=html --root "$PWD/$SRC" "$wrapper" "$BUILD/$typ.html"

  mkdir -p "$(dirname "$out")"
  {
    printf -- '---\n'
    printf 'layout: page\n'
    printf 'title: "%s"\n' "$title"
    printf 'permalink: %s\n' "$perm"
    [ -n "$extra" ] && printf '%s\n' "$extra"
    printf -- '---\n\n'
    printf '<link rel="stylesheet" href="/assets/css/roadmap.css">\n\n'
    printf '{%% raw %%}\n\n<div class="rd-content">\n\n'
    python3 tools/typst-html-body.py "$BUILD/$typ.html"
    printf '\n</div>\n\n{%% endraw %%}\n'
  } >"$out"
  echo "✅ $out"
}

# 侧栏 tab：front matter 的 title 必须是 Roadmap（Chirpy 按它查 locale 表得到「路线图」）
page preface.typ       _tabs/roadmap.html         "/roadmap/"               "Roadmap" \
                       $'icon: fas fa-road\norder: 5'
page 00-direction.typ  roadmap/00-direction.html  "/roadmap/00-direction/"  "方向选择：三方向轮转公测"
page 01-foundation.typ roadmap/01-foundation.html "/roadmap/01-foundation/" "共同底座：CSAPP 与系统基础"
page 02-backend.typ    roadmap/02-backend.html    "/roadmap/02-backend/"    "主线 A：后端开发 · 基础架构"
page 03-ai-infra.typ   roadmap/03-ai-infra.html   "/roadmap/03-ai-infra/"   "主线 B：AI Infra · 高性能计算"
page 04-ml-agent.typ   roadmap/04-ml-agent.html   "/roadmap/04-ml-agent/"   "主线 C：机器学习 · Agent"
page 05-plan.typ       roadmap/05-plan.html       "/roadmap/05-plan/"       "周计划与里程碑（大二上 → 秋招）"
page 06-resources.typ  roadmap/06-resources.html  "/roadmap/06-resources/"  "资源清单与避坑"
page 07-progress.typ   roadmap/progress.html      "/roadmap/progress/"      "进度追踪"

echo
echo "完成：PDF 1 个 + 网页 9 个。commit 前建议跑一次 bash tools/local-preview.sh --build 自检。"
