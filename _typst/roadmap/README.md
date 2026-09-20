# 《CS 成长路线图》Typst 版

这是把 `roadmap/`（Jekyll 页面）那套路线图重新排版成 **A4 PDF** 的 Typst 工程。
产物：`assets/roadmap/cs-roadmap.pdf`，由 [`_tabs/roadmap.md`](../../_tabs/roadmap.md) 提供下载入口。

## 目录结构

```
_typst/roadmap/
├── main.typ              # 主入口：封面 + 目录 + 依次 include 各章
├── lib.typ               # 版式与构件（配色、页眉页脚、标题样式、#note/#tbl/…）
├── CONVERT-RULES.md      # Markdown → Typst 的转换规范（改内容前先读）
├── preface.typ           # 总览：怎么用这份路线图
├── 00-direction.typ      # 方向选择：三方向轮转公测   ← 风格样本
├── 01-foundation.typ     # 共同底座：CSAPP 与系统基础
├── 02-backend.typ        # 主线 A：后端开发 · 基础架构
├── 03-ai-infra.typ       # 主线 B：AI Infra · 高性能计算
├── 04-ml-agent.typ       # 主线 C：机器学习 · Agent
├── 05-plan.typ           # 周计划与里程碑
├── 06-resources.typ      # 资源清单与避坑
└── 07-progress.typ       # 进度追踪
```

## 编译

```bash
bash tools/build-roadmap-pdf.sh                  # 推荐：自动找 typst，输出到 assets/roadmap/
# 或直接：
typst compile _typst/roadmap/main.typ out.pdf
typst watch   _typst/roadmap/main.typ out.pdf    # 边改边看
```

依赖 **typst ≥ 0.13**（本机用 0.15.1）。中文字形默认走 `Droid Sans Fallback`，
Latin 走 `DejaVu Sans`，代码走 `DejaVu Sans Mono`——字体列表在 `lib.typ` 的 `set text(font: …)` 里，
换成 Noto Sans CJK / 思源黑体只需改这一处。

## 版式构件（`lib.typ`）

| 构件 | 用途 |
|---|---|
| `#note[ … ]` | 提示框（对应 Markdown 的 `>` 引用块） |
| `#tbl(列宽, 表头…, 数据…)` | 表格，自动斑马纹与表头分隔线 |
| `#todo[x]` / `#done[x]` | ☐ / ☑ 勾选项（对应 `- [ ]` / `- [x]`） |
| `#no[x]` | ✗ 反例条目（对应 Markdown 里以 ❌ 开头的条目） |

章节文件只写内容（`= 章` / `== 节` / `=== 小节`），**不要**在章节里写版式。

## 已知取舍

- 本机 CJK 字体只有 `Droid Sans Fallback`，**没有粗体字面**，所以 `*强调*` 是用「字重 + 极细描边」模拟的；
  换成带 Bold 的中文字体后可以去掉 `lib.typ` 里 `show strong` 的 `stroke`。
- `❌`（U+274C）本机字体没有覆盖，统一改用 `✗`（由 `#no` 提供）。
- 正文里的英文双引号必须写成 `「」`——Typst 里 `"` 是字符串定界符，直接写会编译报错。

## 与 Markdown 版的关系

| 位置 | 角色 |
|---|---|
| `roadmap/*.md`（Jekyll 页面） | 网页版，负责站内导航与检索 |
| `_typst/roadmap/*.typ` | PDF 版源文件，负责排版与打印 |

两套内容是同一份材料的两种呈现，**改内容时两边都要动**；`CONVERT-RULES.md` 记录了对应的写法。
