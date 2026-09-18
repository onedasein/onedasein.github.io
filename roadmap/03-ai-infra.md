---
layout: page
title: "主线 B：AI Infra · 高性能计算"
permalink: /roadmap/03-ai-infra/
---


> 一句话：**AI Infra = 系统功底 ∩ 机器学习**。门槛高、供给少、溢价高，本科生能拿出真作品的人极少——
> 这是三个方向里"差异化收益"最大的一个，也是**最不能靠看视频学会**的一个。

---

## 1. 能力地图

```
L5  编译栈与自定义硬件：TorchInductor / TVM / MLIR / Triton 编译器、NPU 适配
L4  分布式训练与推理系统：TP/PP/DP/EP、NCCL 通信、PagedAttention、调度与 batching
L3  单卡 Kernel 工程：FlashAttention、融合算子、量化 kernel、CUDA Graph
L2  并行计算与体系结构：SIMT、内存层次、occupancy、Roofline、Tensor Core
L1  C/C++ 与 GPU 编程基础：CUDA C、nvcc、nsys/ncu
L0  ML 基础 + Python：张量、自动微分、Transformer 结构
```

**关键**：L0 不能缺（否则你不知道在优化什么），L1/L2 是护城河（大多数 ML 工程师卡在这里）。

---

## 2. 阶梯与产出

### 阶梯 0：ML 基础（3–4 周，可与主线 C 共用）
- 会写：手推反向传播 + 用 numpy 手写一个两层 MLP 的训练循环。
- 懂结构：Transformer 的每个张量 shape、attention 的复杂度来源、KV Cache 为什么存在。
- 产出去处：见 [04 主线 C 机器学习与 Agent](/roadmap/04-ml-agent/) 的 C1。

### 阶梯 1：CUDA 编程（6–8 周，硬核期）
| 任务 | 产出 |
|---|---|
| 官方 [CUDA C Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/) 通读 + 示例跑通 | 笔记 |
| kernel 三件套：vector add → **reduce**（多级归约）→ **sgemm**（tiling + shared memory + 寄存器分块） | repo + 与 cuBLAS 的 GFLOPS 对比 |
| 用 `ncu` 分析：occupancy、bank conflict、访存合并、Tensor Core 利用率 | 每版 kernel 的性能报告 |
| 手写 softmax / layernorm / 量化反量化 kernel | 融合 kernel 库雏形 |

**核心概念（必须能自己讲清）**：warp/warp divergence、shared memory bank conflict、coalesced access、
occupancy 与寄存器压力、`__syncthreads`、异步拷贝（cp.async）、warp shuffle。

### 阶梯 2：性能建模（2–3 周，决定你是"调参"还是"工程师"）
- **Roofline 模型**：算清楚一个算子的 arithmetic intensity，判断它是 compute-bound 还是 memory-bound。
- **Amdahl 定律 / 数据搬运成本**：为什么算子融合能赢？为什么 attention 要 flash 化？
- 会用 `nsys` 看 timeline（kernel 之间的空隙 = 优化空间）、`ncu` 看单 kernel 指标。
- **产出**：一张自己的 Roofline 图 + "我的 sgemm 只有 cuBLAS 的 X%，因为 ……" 的分析。

### 阶梯 3：AI 编译与算子库（4–6 周）
- **[Triton](https://triton-lang.org/)**：写 fused attention / layernorm / matmul，对比手写 CUDA 的开发效率。
- 读 [FlashAttention](https://github.com/Dao-AILab/flash-attention) 论文 + 源码，理解 tiling 与 online softmax。
- 了解 TorchInductor / TVM / MLIR 的定位（**先了解，别一头扎进编译器**，那是另一个大坑）。

### 阶梯 4：分布式训练（6–8 周）
| 内容 | 关键点 |
|---|---|
| 数据并行 / DDP / **FSDP** | 梯度 all-reduce、参数分片、通信-计算 overlap |
| 张量并行 TP / 流水并行 PP / 专家并行 EP | Megatron 的切分方式、PP 的 bubble |
| 集合通信 | NCCL 的 ring/tree、`all_reduce` vs `reduce_scatter`+`all_gather` |
| 显存与效率 | activation checkpointing、ZeRO 三阶段、混合精度、吞吐（tokens/s/GPU） |

**产出**：单机多卡（哪怕 2 卡）跑通一次 FSDP，给出吞吐随卡数/精度/切分方式的对比表，指出瓶颈在哪。
**资源**：[Megatron-LM](https://github.com/NVIDIA/Megatron-LM)、[DeepSpeed](https://github.com/microsoft/DeepSpeed)、
[PyTorch Distributed 文档](https://pytorch.org/docs/stable/distributed.html)、论文《ZeRO》《Megatron-LM》《FlashAttention》。

### 阶梯 5：推理系统（6–8 周，就业最直接的一段）
| 内容 | 关键点 |
|---|---|
| [vLLM](https://docs.vllm.ai/) | PagedAttention、continuous batching、前缀缓存（prefix caching） |
| SGLang / TensorRT-LLM | RadixAttention、编译优化 |
| 量化 | GPTQ / AWQ / FP8 / INT4，精度-速度权衡 |
| 服务指标 | TTFT、TPOT、吞吐（tokens/s）、并发下的延迟曲线、显存占用 |
| 自研 | **自己实现一个最小 continuous batching 调度器**（这是最好的面试话题） |

**产出**：一份完整的推理服务调优报告：QPS-延迟曲线、量化前后对比、batch size 扫描、瓶颈归因。

---

## 3. 硬件现实（决定你能走多远）

| 条件 | 能做什么 |
|---|---|
| 只有 CPU | 能做：算子优化（SIMD/AVX）、量化推理（llama.cpp）、Roofline 建模、分布式训练的理论与代码阅读 |
| 有 1 张消费级 GPU（8–24GB） | 能做：全部 CUDA/Triton kernel 工作、小模型分布式（2 卡 FSDP）、7B 量化推理 |
| 有云上按小时租的卡（AutoDL/恒源云等） | 上述全部 + 多卡训练实验；**按小时计费，先本地写好再上机** |

**不要**因为"没有卡"就不开始：阶梯 1–3 全部只需要一张卡，甚至 CPU 上的 SIMD 优化都能学到 80% 的性能工程思维。

---

## 4. 自测清单（面试高频）

- 为什么 shared memory 能加速？什么情况下反而变慢？（bank conflict）
- 一个算子 10 TFLOPs，另一个 200 GB/s 带宽，怎么判断哪个更快？Roofline 怎么说？
- FlashAttention 相比标准 attention，省的是什么？（HBM 读写次数，不是 FLOPs）
- 为什么大模型训练必须用 `reduce_scatter + all_gather` 而不是 `all_reduce`？
- PagedAttention 解决了什么问题？（KV Cache 的显存碎片与浪费）
- continuous batching 为什么能把吞吐提高数倍？代价是什么？（单请求延迟）
- 训练吞吐低，你怎么定位？（GPU 利用率 → timeline 空隙 → 数据加载 → 通信 → 算子效率）

---

## 5. 资源

- 课：[CMU 15-418](https://www.cs.cmu.edu/~418/) / UIUC ECE408（并行体系结构）｜[CUDA C Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
- 书：《Programming Massively Parallel Processors》(PMPP，CUDA 圣经)｜《计算机体系结构：量化研究方法》选章
- 工具链：`ncu`、`nsys`、`nvprof`、`cuobjdump`、`nvidia-smi dmon`
- 论文（按顺序精读）：Attention Is All You Need → FlashAttention v1/v2 → ZeRO → Megatron-LM → PagedAttention(vLLM) → MoE 相关
- 社区：`llm-perf`、Triton/CUDA 的 GitHub issue 区（比教程更真实的问题库）

## 6. 方向 B 的毕业作品
> ① 手写 FlashAttention 级 kernel + ncu 报告；② 2 卡 FSDP 吞吐优化报告；
> ③ vLLM 推理服务调优报告 + 自研最小 continuous batching 调度器；④ 一篇拆解论文的 writeup。
> 这套组合在本科实习生里属于前 1%。
