#import "lib.typ": *

= 进度追踪

#note[
  规则：*每周日更新*。勾选只认「有 commit / 有产出」。不许勾「看完了」。
  状态标记：`[ ]` 未开始 ｜ `[~]` 进行中 ｜ `[x]` 完成（附链接/日期）
]

*当前学期*：大二上（2026.9 – 2027.1）
*当前主线*：未定（轮转公测中）
*当前副线*：—
*上次复盘日期*：2026-09-18

== 0. 每周记录（每周一行）

#tbl(
  (auto, auto, 1.5fr, auto, auto, 1fr, 1.2fr),
  [周], [日期], [主要产出], [commits], [writeup], [卡点], [下周第一动作],
  [1], [], [], [], [], [], [],
  [2], [], [], [], [], [], [],
  [3], [], [], [], [], [], [],
)

== 1. 大二上 · 底座

- #todo[开发环境搭建（Linux / gcc / gdb / git / Makefile / CMake）]
- #todo[C 语言五阶段（指针→内存→链接→syscall→并发）]
- #todo[mini shell（管道 + 重定向）]
- #todo[生产者-消费者队列（TSan 无告警）]
- #todo[CSAPP 第 1–2 章 + *Data Lab*]
- #todo[CSAPP 第 3 章 + *Bomb Lab*]
- #todo[CSAPP 第 3 章 + *Attack Lab*]
- #todo[CSAPP 第 5 章（性能优化）]
- #todo[CSAPP 第 6 章 + *Cache Lab*]
- #todo[CSAPP 第 9 章 + *Malloc Lab*]
- #todo[CSAPP 第 8 章 + *Shell Lab*]
- #todo[CSAPP 第 10/12 章 + *Proxy Lab*]
- #todo[线代补课（MIT 18.06 选看）]

== 2. 大二上 · 三方向轮转探针

=== 探针 A · 后端/系统

- #todo[A1 C 写 epoll HTTP 服务器（keep-alive / 超时 / 静态文件）]
- #todo[A2 wrk 压测 + perf 定位 + 一轮优化（附前后对比）]
- #todo[A3（加分）Go 小服务 + etcd 注册 + 优雅重启]
- #todo[repo + README + 200 字感受]

=== 探针 B · AI Infra/HPC

- #todo[B1 CUDA `reduce` kernel（多级归约）]
- #todo[B2 CUDA `sgemm`（tiling + shared memory）+ 与 cuBLAS 对比 GFLOPS]
- #todo[B3 `ncu` 剖析 + Roofline 图]
- #todo[B4 Triton fused LayerNorm]
- #todo[B5（加分）vLLM 跑 7B + nsys timeline]
- #todo[repo + 分析报告]

=== 探针 C · ML/Agent

- #todo[C1 手写反向传播（numpy，不用 autograd）]
- #todo[C2 nanoGPT 复现 + 训练一个字符级模型]
- #todo[C3 mini agent（3 个工具 + ReAct 循环 + 20 条 eval）]
- #todo[C4（加分）LoRA 微调 0.5B 做分类，对比 zero-shot]
- #todo[repo + loss 曲线 + eval 报告]

=== 决策

- #todo[填写评分表（主观 4 项 + 客观 3 项）]
- #todo[写 500 字决策备忘（选择 / 理由 / 退出条件）]
- #todo[*主攻方向确定*：\_\_\_\_\_\_\_\_\_\_（日期：\_\_\_\_\_\_）]

== 3. 大二下 目标（2027.2 – 2027.7）

- #todo[CS144 完成（自己实现 TCP）]
- #todo[Go 语言上手（能写小服务）]
- #todo[6.824 Lab 1 MapReduce]
- #todo[6.824 Lab 2 Raft（含快照）]
- #todo[6.824 Lab 3 KV Server]
- #todo[主攻方向项目 v0.1]
- #todo[主攻方向项目 v1.0（含 benchmark / 消融 / writeup）]
- #todo[*投递日常实习 ≥20 家*]
- #todo[面试 ≥3 场（记录每场问题与复盘）]

== 4. 大三上 目标（2027.9 – 2028.1）

- #todo[6.824 Lab 4 Sharded KV]
- #todo[简历重构（一页 / 项目数据化 / STAR）]
- #todo[日常实习投递（大厂）+ 面试]
- #todo[*拿到一段实习经历*]
- #todo[12 月起投 2028 暑期实习 ≥15 家]
- #todo[按面试反馈补短板（记录清单）]

== 5. 大三下 → 秋招（2028.2 – 2029.1）

- #todo[暑期实习面试（每场 24h 内复盘）]
- #todo[拿到暑期实习 offer]
- #todo[暑期实习 + 争取 return offer]
- #todo[秋招投递与上岸]

== 6. 决策备忘（写完粘贴到这里）

```
日期：
主攻方向：
主攻理由（用数据）：
副线：
退出条件（什么情况下我会重新评估）：
三个月后的里程碑：
```

== 7. 面试复盘记录

#tbl(
  (auto, 1.2fr, 1.6fr, 1.4fr, auto),
  [日期], [公司/岗位], [被问倒的问题], [24h 内的补救动作], [完成],
  [], [], [], [], [],
)

== 8. 「我不喜欢 / 我不擅长」清单（同样值钱）

- （例：不喜欢只调参不看指标；不喜欢长时间没有确定性的调试……）
