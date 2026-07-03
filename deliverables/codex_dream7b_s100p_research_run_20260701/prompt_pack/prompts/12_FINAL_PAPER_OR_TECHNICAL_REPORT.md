# 12 FINAL PAPER OR TECHNICAL REPORT

请基于最新 gate packet 写一份中文技术报告或论文草稿。

## 报告主题

```text
Dream7B diffusion 在 S100P 上的分层证实/证伪研究
```

## 必须先读取

```text
01_final_evidence/dream7b_s100p_gate_packet_v2.json
01_final_evidence/dream7b_s100p_gate_packet_v2.md
reports/*.md
```

## 写作要求

1. 不得声称所有 diffusion model 都不能部署到 S100P。
2. 不得把 runtime pass 写成 accurate deployment pass。
3. 不得把 GGUF Q4_K_M mismatch 写成 BF16 ground-truth mismatch，除非 BF16 reference compare 已经完成并失败。
4. Gate 3/4 未运行时必须写 pending/blocked，不得写 failed。
5. seq16 evidence 只能作为 negative control 和 boundary condition。
6. 明确区分：
   - compile feasibility
   - board load/run/shape validity
   - logits numerical validity
   - generation quality
   - product route validity
7. 每个 claim 后面必须引用对应 report 文件和字段名。

## 报告结构

```text
标题
摘要
关键词
引言
系统与部署背景
分层证伪方法
实验设计
结果
根因定位
讨论
局限性
后续工作
结论
```

## 结论必须是以下四类之一

```text
A. accurate deployment supported
B. deployment falsified against BF16 reference
C. deployment blocked against deployment reference but BF16 unresolved
D. inconclusive due to missing artifact/reference/input alignment
```
