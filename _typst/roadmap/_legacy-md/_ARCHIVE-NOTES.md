# 归档说明：路线图的 Markdown 原稿（v1）

本目录里的 9 个 `.md` 是 **2026-09-18** 写的 Markdown 版路线图，当时发布为 `/roadmap/` 下的
9 个 Jekyll 页面。**2026-09-20** 内容被重写为 Typst（见上一级目录），网页版与 PDF 现在都由
Typst 源生成，因此本目录归档、**不再维护**。

| 归档文件 | 现在对应的 Typst 源 | 页面 URL |
|---|---|---|
| `README.md`（原稿总览） | `preface.typ` | `/roadmap/` |
| `00-方向选择与轮转公测.md` | `00-direction.typ` | `/roadmap/00-direction/` |
| `01-共同底座-CSAPP与系统.md` | `01-foundation.typ` | `/roadmap/01-foundation/` |
| `02-主线A-后端与基础架构.md` | `02-backend.typ` | `/roadmap/02-backend/` |
| `03-主线B-AI-Infra与HPC.md` | `03-ai-infra.typ` | `/roadmap/03-ai-infra/` |
| `04-主线C-机器学习与Agent.md` | `04-ml-agent.typ` | `/roadmap/04-ml-agent/` |
| `05-周计划与里程碑.md` | `05-plan.typ` | `/roadmap/05-plan/` |
| `06-资源与避坑.md` | `06-resources.typ` | `/roadmap/06-resources/` |
| `progress.md` | `07-progress.typ` | `/roadmap/progress/` |

## 为什么保留

1. Markdown 形式在全文检索、复制粘贴、喂给其它工具时更方便；
2. 万一将来想退回 Markdown 工作流，这里有完整原稿；
3. 当年从 Markdown 转 Typst 的逐条规范见上级目录的 `CONVERT-RULES.md`。

## 纪律

**不要在这里改内容。** 改内容请改 `../*.typ`，然后：

```bash
bash tools/build-roadmap.sh     # 重新生成网页 + PDF
```

（本目录位于 `_typst/` 之下，Jekyll 会忽略它，不会被发布到站点。）
