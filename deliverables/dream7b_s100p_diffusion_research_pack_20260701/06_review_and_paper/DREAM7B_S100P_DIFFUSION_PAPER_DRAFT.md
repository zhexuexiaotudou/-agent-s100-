# 运行可行不等于准确部署：Dream7B 扩散模型在 S100P 上的分层证伪研究

## 摘要

边缘 NAS 设备正在承担本地模型服务、隐私数据处理和自动化代理入口的角色，但模型能在板端运行并不等价于模型能准确服务用户请求。本文以 Dream7B 扩散模型在 S100P 上的部署为案例，构建一条分层证据链：编译可行性、板端运行有效性、logits 数值有效性、生成质量有效性和产品路由有效性。实验显示，seq128 B=1 lm_head q16 的分段 HBM 包通过编译证据和 S100P 板端运行证据；代表段 `0`、`5`、`27` 以及完整 28 段链路均可加载运行，最终输出形状为 `[1,152064]`。同一部署路径在数值 gate 上失败：相对可用 GGUF Q4_K_M dump-logits 参考，BPU 输出在两个 128-token 测例上得到 `top1_agreement=0.0`、`ref_top1_in_bpu_top5=0.0`、`mean_cosine=0.0` 和 `max_bpu_normalized_entropy=1.0`。该结果证实了运行可行性，也证伪了当前测试路径的准确部署条件。本文的结论是有限的：它不证明所有扩散模型不能部署在 S100P 上；它证明当前 Dream7B seq128 BPU 路径不能进入生成质量和产品路由阶段。

## 关键词

Dream7B；S100P；扩散语言模型；HBM；BPU；数值验证；边缘部署；OpenClaw

## 引言

边缘 NAS 上的本地模型服务需要同时满足隐私、可用性和可回滚性。用户把文件检索、对话入口和自动化操作交给本地设备时，系统不能只证明模型进程存在，还必须证明每一层部署证据都支撑最终回答质量。对 S100P 这类板端环境而言，编译、加载、运行和生成质量之间存在明显断层。

Dream7B 扩散模型暴露了这个断层。它不是标准自回归 prefill/decode 路径，而是通过掩码序列的反复去噪生成文本。S100P 的官方聊天运行时并未直接覆盖 Dream 架构，因此工程路径需要把模型切成固定长度的 HBM 前向图，再由主机侧执行扩散采样循环。这个结构把“能跑一段 HBM”与“能生成正确 token”分开了。

本文采用“分层证伪链”来限定结论。该方法把部署问题拆成五个 gate：`compile_feasible` 检查 HBM 产物是否完整可信；`s100p_runtime_valid` 检查板端能否加载并执行链路；`logits_numerically_valid` 检查 BPU logits 是否与参考路径对齐；`generation_quality_valid` 检查真实 prompt 输出；`product_route_valid` 检查 OpenClaw 前台路由、回退和回滚。任何 gate 失败都只证伪当前层，不外推为“扩散模型完全不能上 S100P”。

本文给出三点结果。第一，seq128 B=1 lm_head q16 HBM 包通过编译证据，SHA256 与 manifest 一致，28 个 HBM 片段完整。第二，该包通过 S100P 运行 gate，代表段和完整 28 段链路均返回预期 shape。第三，该包未通过 logits 数值 gate，BPU 输出呈现近均匀分布，无法支持继续做生成质量和产品路由测试。这个结果把争议从“能不能运行”推进到“运行结果是否数值可信”。

## 系统与部署背景

Dream7B 的 S100P 路径由分段 HBM 图和主机侧控制逻辑共同组成。云端编译流程生成 seq128 B=1 的 28 个分段 HBM 文件，其中最终段为 `27:28 lm_head_w_bits=16 final_logits_mode=last-token`。该设计降低了全序列 logits 的输出压力，但仍要求最终 logits 在 token 排序和分布形态上与参考实现对齐。

OpenClaw 部署采用双轨边界。产品 Route A 保持 `OpenClaw -> 18888 -> diffuse-resident/GGUF`，它承担默认前台对话路径。研发 Route B 只能使用隔离入口 `18889` 或内部实验脚本，不能覆盖 `18888`，不能把前台回复切到 BPU，也不能删除 seq16 queue baseline。这个边界防止实验路径把未验证的数值行为传播到用户请求。

seq16 证据在本文中只作为负控。既有报告显示，固定 16-token 窗口会造成 prompt tail 截断和 mask 位不足，且旧 BPU logits 路径出现过乱码、饱和和校准问题。这些现象不能证明 seq128 也失败，但它们说明“能运行 HBM”不足以推出“能对话”。seq128 的研究必须重新经过板端运行和数值验证。

## 分层证伪方法

分层证伪链把准确部署定义为 gate 序列，而不是单个成功信号。`compile_feasible` 需要 artifact hash、manifest、summary 和片段数量一致。`s100p_runtime_valid` 需要代表段与完整链路在板端加载运行，并返回预期 shape。`logits_numerically_valid` 需要同输入参考 logits 与 BPU logits 在 top-k、余弦相似度、概率集中度和熵上通过阈值。`generation_quality_valid` 需要预注册 prompt battery 不出现乱码、空答和 token 泄漏。`product_route_valid` 需要隔离入口、前台回退、健康检查、队列排空和回滚证据。

该方法的关键是停止规则。只要某个 gate 失败，后续 gate 不再执行，也不标记为失败。这个规则避免把“未测试”写成“失败”，也避免把低层成功外推为产品可用。对本研究而言，Gate 2 失败后，生成质量和产品路由保持 pending。

数值 gate 使用四个部署阻断指标。top-1 agreement 检查参考首选 token 是否一致；reference top-1 in BPU top-5 检查 BPU 是否至少保留参考首选 token；logits cosine 检查向量方向；normalized entropy 和 top-1 probability 检查输出是否接近均匀分布。阈值设定为 top-1 agreement 不低于 0.80、reference top-1 in BPU top-5 不低于 0.95、mean cosine 不低于 0.95、max normalized entropy 不高于 0.95。

## 实验材料与证据来源

实验材料来自 2026-06-23 的 seq128 云端编译产物和 2026-07-01 的 S100P 板端验证。artifact metadata 记录 `model=Dream7B`、`target=S100 nash-e`、`seq_len=128`、`batch_size=1`、`w_bits=8`、最终段 `lm_head_w_bits=16`、`segment_count=28`、`hbm_count=28`、`missing_or_bad=[]`。tar 的 SHA256 为 `c0e7d6c31af17871cf550ceec88c1bf1ec8de33f30f4d75a9f7b31aa1b73e1b1`。

板端运行证据来自 `seq128_s100p_runtime_gate.json`。该报告运行在 `/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken`，使用 HBRT runtime `3.13.6_(4.7.5 HBRT)`。代表段选择 `0`、`5` 和 `27`，分别覆盖 embedding、隐藏层和最终 logits 段；完整链路执行全部 28 个 segment。

数值证据来自 `seq128_logits_reference_compare.json`。该报告使用 `/mnt/nas/openclaw/runtimes/diffuse-cpp/build/dump-logits` 读取 `/mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf`，生成 GGUF Q4_K_M 参考 logits。BPU 路径对相同 token 序列运行完整 seq128 HBM 链，并比较最后一个 token 的 logits。该参考不是 BF16 CPU 参考，因此本文把它作为部署阻断控制，而不是最终数学等价性证明。

## 结果

### 编译证据证明 seq128 HBM 包完整

Gate 0 通过。最终 packet 记录 tar 的 expected SHA256 与 actual SHA256 完全一致，artifact summary 记录 28 个 segment 和 28 个 HBM 文件，且 `missing_or_bad=[]`。云端 closure 文档也记录 full `seq128, B=1` segmented compile 通过，28/28 HBM 完成。

**Takeaway.** seq128 已不再只是计划中的候选路径；它具备可复核的编译产物和 artifact provenance。

### S100P 运行证据证明链路可加载执行

Gate 1 通过。runtime gate 返回 `ok_dream7b_seq128_s100p_runtime_gate`。代表段执行 3 个 segment，完整链路执行 28 个 segment，最终 shape 为 `[1,152064]`。报告记录 representative total load/run 为 `25191.438 ms` 和 `80.688 ms`，full-chain total load/run 为 `75503.263 ms` 和 `317.142 ms`，wall time 为 `101579.41 ms`，未观察到 resource exhausted。

**Takeaway.** S100P 能加载和执行该 seq128 分段 HBM 链路；运行成功本身已经被证实，但它仍未证明 logits 正确。

### Logits 数值证据证伪当前 BPU 路径

Gate 2 失败。GGUF Q4_K_M 参考与 BPU last-token logits 在 `zeros` 和 `ramp` 两个 128-token 测例上完全不对齐。汇总指标为 `top1_agreement=0.0`、`ref_top1_in_bpu_top5=0.0`、`mean_cosine=0.0`、`min_cosine=0.0`、`mean_bpu_top1_probability=6.576178451178451e-06`、`max_bpu_normalized_entropy=1.0`。两个 case 的 GGUF top-1 均为 `151643`，BPU top-1 均为 `152063`。

| Case | GGUF top-1 | BPU top-1 | Top-1 match | Reference top-1 in BPU top-5 | Cosine | BPU top-1 probability | BPU normalized entropy |
| --- | ---: | ---: | --- | --- | ---: | ---: | ---: |
| `zeros` | 151643 | 152063 | False | False | 0.000000 | 0.000007 | 1.000000 |
| `ramp` | 151643 | 152063 | False | False | 0.000000 | 0.000007 | 1.000000 |

**Takeaway.** 当前 BPU logits 路径没有提供可用 token 排序信号；在这个 gate 失败前，任何生成质量或产品路由测试都会把低层数值错误包装成上层体验问题。

### 产品边界保持隔离

Gate 3 和 Gate 4 未执行。研究过程没有启用 `18889`，没有把前台 OpenClaw 回复路由到 BPU，没有覆盖 `18888`，也没有删除 seq16 artifacts。最终研究记录显示实验后无 `18889`、seq128 probe 或 dump-logits 残留进程，seq128 HBM 文件数为 28，seq16 目录仍保留。

**Takeaway.** 该研究没有把失败的数值路径推进到用户可见服务；实验结论停在证据链内，而不是污染产品路由。

## 讨论

本研究的核心发现是“运行可行”与“准确部署”之间存在可测断层。S100P 能执行完整 seq128 HBM 链路，说明编译和 runtime 适配工作已经跨过了结构性门槛。Logits gate 失败说明这个门槛不足以支持模型生成。对扩散语言模型而言，每一步去噪都依赖 logits 排序和置信度；当 last-token logits 接近均匀分布时，采样循环缺少有效信号。

GGUF Q4_K_M 参考的角色需要准确表述。它是当前可用的产品参考路径，也是阻断前台部署的合理控制。BPU 路径若不能与该参考保持基本 top-k 和分布一致，就不能替代或补充现有产品路径。与此同时，GGUF Q4_K_M 不是 BF16 CPU 参考；因此本文不能把数值失败直接归因到 HBM 图本身，也不能排除参考量化差异、最终段后处理、输出 scale 或 runtime 解析错误。

seq16 负控说明了为什么分层证据必要。旧 seq16 路径暴露出固定窗口截断、mask 位不足和 logits 异常，产品默认路径因此保留在 `18888` 的 GGUF resident 服务上。seq128 解决了窗口长度的一部分结构问题，但它必须独立通过数值 gate。本文结果表明，更长上下文和可运行链路没有自动消除 logits 层风险。

该方法也给出产品决策边界。若只报告 “28 段跑通”，团队可能会把 seq128 当作可部署候选；若只报告 “不能部署”，团队又会忽略已经解决的编译和 runtime 问题。分层证伪链把结论定位在具体失败层：当前路径不是 compile failure，也不是 board runtime failure，而是 logits numerical failure。

## 局限性

第一，数值参考来自 GGUF Q4_K_M dump-logits，而不是 BF16 CPU 或 PyTorch 参考。该参考足以阻断部署，但不足以定位最终数学误差来源。

第二，logits gate 只覆盖 `zeros` 和 `ramp` 两个 128-token case。它们足以暴露严重异常，但不能替代完整 prompt battery。

第三，Gate 3 和 Gate 4 没有执行。本文不声称 seq128 生成质量失败，也不声称产品路由失败；它只说明这两个 gate 在数值失败后不应继续推进。

第四，本文只评估当前 Dream7B seq128 B=1 lm_head q16 分段 HBM 路径。结论不能外推到所有 Dream7B 编译配置、所有扩散模型或所有 S100P runtime 版本。

## 后续工作

下一步应定位 Gate 2 失败来源。首先，检查 `seg27_28` 的 raw int16 输出，确认它是否在 dequantization 前已经呈现近均匀或全零特征。其次，捕获进入最终段的 hidden tensor，并在相同 hidden 输入上比较 BPU 最终段与 BF16/PyTorch `lm_head` 输出。第三，验证 `lm_head_w_bits=16` 与 `last-token` 组合是否改变了模型名、输出 scale、shape 或后处理路径。第四，在修复后重复 top-k、cosine、entropy gate，再恢复中文 prompt battery 和 `18889` 隔离路由测试。

后续论文版本还应加入更细的错误归因实验。可选实验包括逐段 hidden state cosine、最终段单独替换、GGUF 与 BF16 的参考差异量化，以及真实中文 prompt 下的 token-level 轨迹对比。这些实验能区分三类原因：HBM 图错误、参考路径差异和 runtime 后处理错误。

## 结论

Dream7B 扩散模型在 S100P 上的 seq128 路径已经通过编译和板端运行验证，但没有通过准确部署所需的 logits 数值验证。该结论既肯定了工程进展，也阻止了过早产品化。当前最准确的表述是：Dream7B seq128 BPU 路径在 S100P 上运行可行，但在可用 GGUF Q4_K_M 参考下数值不可信；在解释并修复 logits gate 前，不应进入生成质量测试或前台产品路由。

## 证据来源

- `01_final_evidence/dream7b_s100p_diffusion_research_packet.json`
- `02_primary_reports/seq128_runtime_gate/seq128_s100p_runtime_gate.json`
- `02_primary_reports/seq128_logits_compare/seq128_logits_reference_compare.json`
- `05_artifact_metadata/seq128_b1_lmheadq16_lasttoken_summary.json`
- `03_prior_evidence/docs/dream7b_seq128_cloud_compile_closure_2026-06-23.md`
- `03_prior_evidence/docs/dream7b_openclaw_two_track_deployment_2026-06-22.md`
- `03_prior_evidence/docs/dream7b_bpu_seq16_quality_root_cause_2026-06-22.md`
- `03_prior_evidence/docs/dream7b_bpu_logits_diagnosis_2026-06-22.md`

