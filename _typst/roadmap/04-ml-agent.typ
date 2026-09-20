#import "lib.typ": *

= 主线 C：机器学习 · Agent

#note[
  一句话：这个方向*入门最容易、竞争最激烈、最容易高估自己*。抗跌的做法只有一条：*能把模型训出来、能评测得住、能端到端上线*——而不是会调 API。
]

== 1. 能力地图

```
L4  系统与落地：推理成本、延迟、评测体系、数据飞轮、监控与回归
L3  Agent 工程：工具调用、记忆、规划、多智能体、沙箱与安全
L2  对齐与微调：SFT / LoRA / DPO / 数据构造与清洗
L1  训练：手写反向传播、训练循环、loss 诊断、分布式训练入门
L0  原理与数学：线性代数、概率、梯度、Transformer 结构
```

*残酷事实*：L0/L1 是筛人的（会手推反向传播的人远少于会 import transformers 的人）；L3/L4 是挣钱的（企业现在真正缺的是「能把 Agent 做稳定并评测出来」的人）。

== 2. 阶梯与产出

=== 阶梯 0：原理（3–4 周）

- #link("https://karpathy.ai/zero-to-hero.html")[Karpathy Zero to Hero] 全系列：micrograd（手写自动微分）→ makemore → GPT from scratch。
- 配套：手推一遍反向传播（用 numpy 实现两层 MLP，不许用框架自动求导）。
- *产出*：一个不依赖 PyTorch autograd 的 MLP 训练脚本 + 一篇推导笔记。
- 数学补课：线代（矩阵乘法/特征值直觉）、概率（KL 散度、采样、期望）、微积分（链式法则）。

=== 阶梯 1：训练（4–6 周）

#tbl(
  (1.7fr, 1fr),
  [任务], [关键点],
  [#link("https://github.com/karpathy/nanoGPT")[nanoGPT] 复现并训练一个字符级/小词表模型], [训练循环、学习率调度、梯度裁剪、混合精度],
  [换一个真实数据集（如中文语料），做 tokenizer（BPE）], [数据处理管线、词表、序列打包],
  [诊断训练：loss 不降 / 震荡 / 过拟合，分别怎么办], [这是「会不会做 ML」的分水岭],
)

*产出*：训练日志、loss 曲线、与 baseline 的对比表、失败实验的记录（*失败记录很值钱*）。

=== 阶梯 2：微调与对齐（3–4 周）

- *SFT*：小模型（0.5B–3B）指令微调（LLaMA-Factory / trl）。
- *LoRA / QLoRA*：理解低秩假设、rank 与 α、显存收益。
- *DPO*（及偏好数据构造）；了解 PPO/GRPO 的定位与代价。
- *数据工程*：数据配比、去重、污染检测（eval 集泄漏会让你的成绩一文不值）。
- *产出*：一次完整的「数据 → 训练 → 评测 → 迭代」闭环报告，含消融实验。

=== 阶梯 3：Agent 工程（4–6 周，就业最直接）

#tbl(
  (auto, 1.8fr),
  [主题], [要点],
  [工具调用], [function calling 协议、参数校验、错误恢复、幂等],
  [上下文管理], [长上下文策略、压缩/摘要、检索注入、KV 复用],
  [记忆], [短期（对话）、长期（向量/结构化）、冲突消解],
  [规划], [ReAct / Plan-and-Execute / 反思；何时该放弃自主性改用工作流],
  [多智能体], [分工与通信成本，什么时候它比单 agent 更差],
  [沙箱与安全], [代码执行隔离、提示注入、权限边界（*企业最关心*）],
  [可观测], [trace、token 成本、失败归因],
)

*产出*：一个真实可用的 agent（解决你自己的一个实际问题），带*自建 eval 集*和失败案例分类。

*推荐实现路径*：先手写 ReAct 循环（不依赖框架），再对比 LangGraph/其它框架——*先手写后才能判断框架是否必要*。

=== 阶梯 4：评测与落地（3–4 周，最被低估、最值钱）

- 自建 eval：任务集设计、评分标准、*LLM-as-judge 的偏差与校准*（位置偏差、长度偏差、自我偏好）。
- 指标：pass\@k、准确率、鲁棒性、成本（每任务 token/延迟）。
- RAG 全链路：切分 → embedding → 检索（BM25+向量混合）→ rerank → 生成；每一环的评测与消融。
- 上线：监控、回归测试、A/B、prompt/模型版本管理。

== 3. 自测清单

- 手推 attention 的梯度大致长什么样？为什么需要 `1/√d` 缩放？
- 训练 loss 正常下降但验证集不降，列出至少 5 个可能原因和排查顺序。
- LoRA 为什么有效？rank 越大越好吗？
- DPO 相比 PPO 省了什么？它依赖什么假设？
- 你的 agent 在任务 A 上成功率 60%，怎么知道提升到 80% 是哪一步的功劳？（*消融 + 分层 eval*）
- LLM-as-judge 有什么系统性偏差？怎么缓解？
- 一个 Agent 产品的成本从 0.1 元/次涨到 1 元/次，你怎么排查？

== 4. 资源

- 课：#link("https://karpathy.ai/zero-to-hero.html")[Karpathy Zero to Hero]｜#link("https://cs231n.stanford.edu/")[CS231n]｜#link("https://web.stanford.edu/class/cs224n/")[CS224n]
- 书：《动手学深度学习》(d2l)｜《深度学习》花书（当参考，别通读）｜《Build a Large Language Model (From Scratch)》(Raschka)
- 工具：PyTorch、HF transformers/trl/peft、LLaMA-Factory、#link("https://github.com/karpathy/nanoGPT")[nanoGPT]、vLLM、LangGraph
- 论文：Attention Is All You Need → GPT-3 → InstructGPT → LoRA → DPO → ReAct → Toolformer → RAG 相关
- 评测：HELM、lm-evaluation-harness、SWE-bench、GAIA（读题方式比刷分更重要）

== 5. 方向 C 的毕业作品

#note[
  ① nanoGPT 复现；② 一次完整 SFT→LoRA→DPO 闭环（含消融）；③ 一个真实可用的 agent + 自建 eval + 失败分析；④ 一份「评测方法论」writeup。

  *警告*：如果毕业作品是「用 LangChain 搭了个问答机器人」，那它在简历上等于零。
]

== 6. 方向 C 的最大陷阱

- #no[只用 API，从不训练 → 无法解释模型行为，面试两个问题就穿。]
- #no[只追框架 → 框架半年一换，原理十年不变。]
- #no[只做 demo 不评测 → 无法回答「你怎么知道它变好了」。]
- #no[逃避数学和系统 → 上限被锁死在「应用层调包」。]
