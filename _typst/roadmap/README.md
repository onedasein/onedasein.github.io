# 《CS 成长路线图》Typst 工程（一套源 → 网页 + PDF）

路线图的**唯一内容源**就是这里的 `.typ` 文件。一次构建产出两样东西：

| 产物 | 位置 | 面向 |
|---|---|---|
| 网页版 | `_tabs/roadmap.html` + `roadmap/*.html`（Jekyll 页面） | 站内阅读、检索、被链接 |
| PDF 版 | `assets/roadmap/cs-roadmap.pdf` | 打印、离线、整体通读 |

> 2026-09 起，`/roadmap/` 下的页面由 Typst 的 HTML 导出生成，Markdown 版已移除。

## 目录结构

```
_typst/roadmap/
├── main.typ              # PDF 入口：封面 + 目录 + 依次 include 各章
├── lib.typ               # 版式与构件（双目标：PDF / HTML 都在这里切换）
├── README.md             # 本文
├── CONVERT-RULES.md      # 当年 Markdown → Typst 的转换规范（历史记录）
├── preface.typ           # 总览：怎么用这份路线图
├── 00-direction.typ      # 方向选择：三方向轮转公测
├── 01-foundation.typ     # 共同底座：CSAPP 与系统基础
├── 02-backend.typ        # 主线 A：后端开发 · 基础架构
├── 03-ai-infra.typ       # 主线 B：AI Infra · 高性能计算
├── 04-ml-agent.typ       # 主线 C：机器学习 · Agent
├── 05-plan.typ           # 周计划与里程碑
├── 06-resources.typ      # 资源清单与避坑
├── 07-progress.typ       # 进度追踪
└── _legacy-md/           # 归档：重写前的 Markdown 原稿（不再维护，见其 _ARCHIVE-NOTES.md）
```

## 构建

```bash
bash tools/build-roadmap.sh          # PDF + 9 个网页，一次生成
bash tools/local-preview.sh          # 本地起服务看效果（127.0.0.1:4000/roadmap/）
```

只编译 PDF：`typst compile _typst/roadmap/main.typ out.pdf`
只编译某章 HTML：

```bash
printf '#import "../lib.typ": *\n#show: roadmap-web\n#include "../03-ai-infra.typ"\n' > /tmp/w.typ
typst compile --features html --format html --pretty --input target=html \
  --root _typst/roadmap /tmp/w.typ /tmp/w.html
```

依赖 **typst ≥ 0.13**（HTML 导出需要 `--features html`；本机用 0.15.1）与 python3。

## 双目标是怎么做到的

`lib.typ` 读 `sys.inputs.target`（默认 `paged`），构件按目标切换实现；
网页版的最终组装（front matter、CSS、标题锚点）由 `tools/build-roadmap.sh`
和 `tools/typst-html-body.py` 完成。

| 构件 | PDF 目标 | HTML 目标 |
|---|---|---|
| `#note[…]` | 描边提示框 | `<div class="rd-note">` |
| `#tbl(列宽, 表头…, 数据…)` | 斑马纹表格 | `<table>` + `<thead>` |
| `#todo[…]` / `#done[…]` | ☐ / ☑ | `<span class="rd-todo">` |
| `#no[…]` | 红色 ✗ | `<span class="rd-no"><span class="rd-mark">✗</span>` |
| `#xref("slug", "文字")` | 纯文字 | `<a href="/roadmap/slug/">` |
| `#pdf-banner()` | 不显示 | 顶部 PDF 下载条 |

章节文件只写内容与构件，**不要**在里面写版式，也不要直接 import 别的东西。

## 网页版样式

`assets/css/roadmap.css`（颜色走 Chirpy 主题变量，自动跟随亮/暗色）。
Typst 的 HTML 导出只给语义化标签、不带样式，所以表格/代码块/提示框的观感全靠这个文件。

标题的 `id` 与 `#` 锚点由 `tools/typst-html-body.py` 补上，slug 规则刻意对齐
Kramdown，**保证旧的 `#锚点` 链接不失效**；同时把 Typst 的标题层级上移一级
（Typst 把 `= 章` 映射成 `<h2>`，网页版章标题由 Jekyll 的 title 承担，
所以 `== 节` 需要从 `<h3>` 回到 `<h2>`）。

## 已知取舍

- 本机 CJK 字体只有 `Droid Sans Fallback`，**没有粗体字面**，PDF 里 `*强调*` 是用
  「字重 + 极细描边」模拟的；网页版由浏览器渲染，是真粗体。换成带 Bold 的中文字体后
  可以去掉 `lib.typ` 里 `show strong` 的 `stroke`。
- `❌`（U+274C）本机字体没有覆盖，统一改用 `✗`（由 `#no` 提供）。
- 正文里的英文双引号必须写成 `「」`——Typst 里 `"` 是字符串定界符，直接写会编译报错。
- Typst 的 HTML 导出仍是实验特性，每次编译会刷一条警告，构建脚本已过滤。
- 网页版的 `_tabs/roadmap.html` 的 front matter `title` 必须是 `Roadmap`
  （Chirpy 按它查 locale 表显示成「路线图」），页面 CSS 类名不要改。

## 增改内容的工作流

1. 改 `_typst/roadmap/*.typ`（构件用法见上文表与 `lib.typ` 注释）；
2. `bash tools/build-roadmap.sh` 重新生成 PDF 与网页；
3. `bash tools/local-preview.sh` 本地看一眼，再 commit/push（CI 只做 Jekyll 构建与链接检查）。
