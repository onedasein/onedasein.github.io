// ============================================================
//  main.typ —— 主入口：封面 + 目录 + 全部章节
//  编译： typst compile main.typ out/roadmap.pdf
// ============================================================
#import "lib.typ": *

#show: roadmap-doc

// ---------------- 封面 ----------------
#page(margin: 0pt, header: none, footer: none)[
  #block(width: 100%, height: 100%, fill: accent)[
    #place(center + horizon)[
      #block(width: 76%)[
        #text(size: 9.5pt, fill: rgb("#9dc3e6"))[dasein · 2026-09]
        #v(0.9em)
        #text(size: 31pt, weight: "bold", fill: white, stroke: 0.35pt)[CS 成长路线图]
        #v(0.5em)
        #line(length: 32%, stroke: 1.2pt + rgb("#9dc3e6"))
        #v(1.1em)
        #text(size: 12pt, fill: rgb("#d6e6f5"))[
          后端开发 · 基础架构 ／ AI Infra · 高性能计算 ／ 机器学习 · Agent
        ]
        #v(0.5em)
        #text(size: 10pt, fill: rgb("#9dc3e6"))[
          大二起点 ｜ 四个学期的时间表 ｜ 每个方向的验收标准
        ]
      ]
    ]
  ]
]

// 封面不编号，目录从第 1 页开始
#counter(page).update(1)

// ---------------- 目录 ----------------
#block(above: 0.2em, below: 1.1em)[
  #text(size: 19pt, weight: "bold", fill: accent, stroke: 0.25pt)[目录]
  #v(-0.3em)
  #line(length: 100%, stroke: 1.5pt + accent-2)
]
#outline(title: none, depth: 2, indent: 1.1em)

// ---------------- 正文 ----------------
#include "preface.typ"
#include "00-direction.typ"
#include "01-foundation.typ"
#include "02-backend.typ"
#include "03-ai-infra.typ"
#include "04-ml-agent.typ"
#include "05-plan.typ"
#include "06-resources.typ"
#include "07-progress.typ"
