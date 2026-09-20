// ============================================================
//  lib.typ —— 《CS 成长路线图》PDF 版式定义
//
//  用法（主文件 main.typ）：
//      #import "lib.typ": *
//      #show: roadmap-doc
//      #include "preface.typ"
//      #include "00-direction.typ"
//      ...
//
//  章节文件只写内容，不写版式：`= 标题` / `== 小节` / `=== 子节`。
//  常用构件： #note[...]（提示框）、#tbl(列宽, 表头..., 单元格...)（表格）、
//            #todo[...] / #done[...]（勾选框）、#no[...]（✗ 反例）、
//            #emph-key[...]（中文也可视的加粗强调）。
// ============================================================

// ---- 配色 ----
#let accent = rgb("#1b4f72")      // 主色：深蓝
#let accent-2 = rgb("#2e86c1")    // 副色：亮蓝
#let soft = rgb("#eef4fa")        // 提示框底色
#let ink = rgb("#16202b")         // 正文
#let muted = rgb("#6b7684")       // 次要文字
#let warn = rgb("#b3261e")        // 强调/警示

// ---- 行内构件 ----
// 勾选框（对应 Markdown 的 - [ ] / - [x]）
#let todo(body) = box[#text(fill: muted)[☐] #body]
#let done(body) = box[#text(fill: accent)[☑] #body]
// 反例行（对应 Markdown 里以 ❌ 开头的条目；U+274C 本机无字体覆盖，改用 ✗）
#let no(body) = [#text(fill: warn, weight: "bold")[✗]#h(0.35em)#body]

// 提示框（对应 Markdown 的 > 引用块）
#let note(body) = block(
  width: 100%,
  inset: (left: 11pt, right: 10pt, top: 7pt, bottom: 7pt),
  radius: 2pt,
  fill: soft,
  stroke: (left: 3pt + accent-2, rest: none),
)[#body]

// 表格：第一行视为表头。用法 #tbl((auto, 1fr, 1fr), [表头1], [表头2], [表头3], [a], [b], [c], ...)
#let tbl(cols, ..cells) = {
  let n = cols.len()
  let cs = cells.pos()
  set text(size: 9pt)
  table(
    columns: cols,
    inset: (x: 6pt, y: 4.5pt),
    align: left + top,
    fill: (x, y) => if y == 0 { luma(236) } else if calc.odd(y) { luma(250) } else { white },
    stroke: (x, y) => (
      bottom: if y == 0 { 0.8pt + luma(130) } else { 0.3pt + luma(205) },
    ),
    table.header(..cs.slice(0, n)),
    ..cs.slice(n),
  )
}

// ---- 章节标题状态（供页眉显示当前章名）----
#let chap-state = state("chap", "")

// ---- 文档模板 ----
#let roadmap-doc(
  title: "CS 成长路线图",
  body,
) = {
  set document(title: title, author: "dasein")

  set page(
    paper: "a4",
    margin: (x: 19mm, top: 16mm, bottom: 17mm),
    header: context {
      let c = chap-state.get()
      if c != "" {
        set text(size: 7.8pt, fill: muted)
        grid(
          columns: (1fr, auto),
          align: (left, right),
          [#title],
          [#c],
        )
        v(-0.45em)
        line(length: 100%, stroke: 0.5pt + luma(200))
      }
    },
    footer: context {
      set text(size: 7.8pt, fill: muted)
      grid(
        columns: (1fr, auto),
        align: (left, right),
        [dasein · onedasein.github.io],
        counter(page).display("1"),
      )
    },
  )

  set text(font: ("DejaVu Sans", "Droid Sans Fallback"), size: 10.2pt, fill: ink, lang: "zh")
  set par(justify: true, leading: 0.72em, spacing: 0.92em, first-line-indent: 0em)
  set list(spacing: 0.42em, indent: 1.1em, body-indent: 0.5em)
  set enum(spacing: 0.42em, indent: 1.1em, body-indent: 0.5em)

  // 中文没有粗体字面（本机 CJK 只有 Droid Sans Fallback 常规体），
  // 用「字重 + 极细描边」模拟加粗，保证中英文都能看出强调。
  show strong: it => text(weight: "bold", stroke: 0.03em, it.body)
  show link: it => underline(stroke: 0.4pt + accent-2, text(fill: accent-2, it))
  show raw: set text(font: ("DejaVu Sans Mono", "DejaVu Sans", "Droid Sans Fallback"), size: 8.6pt)
  show raw.where(block: true): it => block(
    width: 100%,
    inset: 8pt,
    radius: 2pt,
    fill: luma(247),
    stroke: 0.4pt + luma(215),
    it,
  )
  show quote: it => note(it)

  // 一级标题 = 章：另起一页 + 主色 + 下划线
  show heading.where(level: 1): it => [
    #chap-state.update(it.body)
    #pagebreak(weak: true)
    #block(above: 0.2em, below: 1.15em)[
      #text(size: 19pt, weight: "bold", fill: accent, stroke: 0.25pt)[#it.body]
      #v(-0.3em)
      #line(length: 100%, stroke: 1.5pt + accent-2)
    ]
  ]
  // 二级标题
  show heading.where(level: 2): it => block(above: 1.25em, below: 0.5em)[
    #text(size: 13.6pt, weight: "bold", fill: accent-2, stroke: 0.2pt)[#it.body]
  ]
  // 三级标题
  show heading.where(level: 3): it => block(above: 1.0em, below: 0.4em)[
    #text(size: 11.4pt, weight: "bold", fill: ink, stroke: 0.18pt)[#it.body]
  ]

  body
}
