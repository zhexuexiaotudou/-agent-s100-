# Dream 7B S100P 部署优化专题

本文档把 Dream 7B 在 S100P 上从 0 到默认可部署的完整推进过程整理成一个独立专题。它不是报告路径堆叠，而是项目亮点视角的工程复盘：官方没有现成 Dream 7B 参考，我们先跑官方 LLM 基线，再迁移到 Dream，最后通过分段 HBM、selected-pair residency、cross-job 队列摊销、默认服务 promotion 和 rollback 验证，把 Dream 7B 推到 S100P 默认服务。

## 汇报版报告

- [dream7b_s100p_deployment_report_2026-06-10.pdf](dream7b_s100p_deployment_report_2026-06-10.pdf): 用于汇报的完整 PDF 报告，突出当前部署结论、技术亮点、卡点归因、可用程度和下一步支持需求。
- [dream7b_s100p_deployment_report_2026-06-10.md](dream7b_s100p_deployment_report_2026-06-10.md): PDF 的 Markdown 源稿，便于后续继续修改汇报口径。

## 当前结论

Dream 7B 已经达到 S100P 默认可部署标准。

- 默认服务：`dream7b-bpu-batch-queue.service`
- 默认队列入口：`/mnt/nas/openclaw/queues/dream7b-bpu`
- 稳定 runtime：`/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default`
- 最终状态：`default_deployable_ready: True`
- 最终验收：`default_deployable_status: ready`

最终 192 请求默认服务遥测：

| 指标 | 结果 | 解释 |
| --- | ---: | --- |
| processed_request_count | 192 | 默认队列 12 个 job，每个 16 请求 |
| failed_job_count | 0 | 长稳态无失败 job |
| load_to_run_ratio | 8.734653 | 低于 9.443895，且低于优先目标 9.0 |
| avg_bpu_loading | 9.915 | 高于 8.811，且高于优先目标 9.0 |
| amortized_wall_ms_per_processed_request | 1441.545 ms | 低于 96 请求长稳退化边界 1451.906 ms |
| max_bpu_loading | 98.0 | 仅作辅助现象，不作为 128TOPS 成功口径 |

最终 acceptance：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
default_deployable_ready: True
default_deployable_status: ready
blockers: []
warnings: []
```

## 为什么这是亮点

老师给出的路线是：先用地瓜官方 SDK 已支持的 LLM 跑通“量化/编译/部署”全流程，再换 Dream 7B 走一遍，卡住就给老师或厂商一个最小复现包。实际推进中，Dream 7B 官方路线确实卡在 SDK registry/model adapter 缺失，但我们没有直接放弃，而是建立了另一条可验证的 segmented HBM 部署路线。

这个亮点不在于“跑了一个模型 demo”，而在于完成了下面这条闭环：

```text
官方 LLM 基线 -> Dream 官方路线失败归因 -> Dream 分段 HBM 执行 -> BPU 队列服务
-> HBM reload 诊断 -> selected-pair residency -> cross-job 摊销
-> 单请求 fallback -> 默认服务 promotion -> rollback 验证 -> 文档一致性验收
```

最终输出不是一次手工推理，而是默认 systemd 服务、默认队列入口、长稳态 telemetry、rollback 和验收探针。

## 从 0 到默认可部署的阶段

### 0. 初始目标

目标是让 Dream 7B 在 S100P 128TOPS BPU 路线上真正可用，而不是只在 CPU 或离线脚本里存在。最初的约束很强：

- 官方 SDK 没有 Dream 7B 现成样例。
- S100P 资源有限，7B 级模型直接官方 runtime 不一定能加载。
- 不能只用 `max_bpu_loading=100.0` 宣称成功。
- 必须有可复现探针、服务化部署、遥测和验收文档。

### 1. 官方 Qwen 基线先跑通

按老师建议，先用官方支持模型建立方法基线。Qwen2.5-1.5B 的 1024/256 高上下文配置在 S100P 上触发 common-buffer/BPU 内存问题；之后切到 512/128 后跑通，成为官方 runnable baseline。

关键结论：

- Qwen2.5-1.5B `cache_len=512, chunk_size=128` 可作为官方小模型基线。
- 1024/256 失败边界明确，问题集中在 common-buffer/BPU 内存分配。
- 这个基线证明工具链和板端环境不是完全不可用。

代表报告：

```text
/mnt/nas/openclaw/reports/models/s100_official_qwen_fullflow_20260609-210514/official_qwen_fullflow_probe.json
runtime_completed: true
runtime_returncode: 0
memory_alloc_failure_observed: false
```

### 2. Dream 7B 官方 oellm_build 路线被确认阻塞

把同样思路迁移到 Dream 7B 时，官方 `oellm_build/leap_llm` 路线卡在 registry/model adapter。DreamModel 不在官方注册表中，这不是环境问题，而是 SDK 缺 Dream adapter。

关键结论：

- Dream 7B 不能直接走官方白名单模型路径。
- 失败阶段是 `registry_missing`。
- 如果要官方完整支持，需要厂商提供 DreamModel adapter、算子映射和量化编译路径。

这一步的价值是把“编译失败”变成了可沟通的最小复现问题，而不是泛泛而谈。

### 3. 走 Dream 分段 HBM 路线

官方路线阻塞后，主线转为 segmented HBM。Dream 7B 被拆成多个 S100/Nash HBM 段，用 Python runtime 和脚本完成 seq16 forward 链路验证。

这一阶段解决的是“真实 Dream 权重能不能进入 S100P BPU 路径”。

结果：

- 真实 Dream 7B 权重进入 BPU HBM 执行路径。
- 形成 base/fine HBM artifact inventory。
- 建立 batch forward、queue runner、systemd service、text queue 等服务基础。

但此时还不是高利用率，主要瓶颈是 HBM 加载远大于 run 时间。

### 4. 诊断 HBM reload dominated

多轮 telemetry 和 window-cost 报告显示，S100P BPU 确实能跑 Dream，但平均 BPU loading 不高，load/run ratio 偏高。问题不是“完全没用上 BPU”，而是 HBM segment 反复加载使整体吞吐被 reload 主导。

早期判断：

```text
diagnosis: hbm_reload_dominated
```

这个诊断决定了后续优化方向：不能只盯 `max_bpu_loading`，必须降低 reload 或把 reload 摊销到更多请求上。

### 5. selected-pair residency

通过 residency matrix、triplet/topology 探针发现，完整多段常驻不现实，但 selected pair `[1, 8]` 可以作为较优的 resident set，覆盖关键 segments：

```text
selected_pair: [1, 8]
selected_segments: ['seg02_04', 'seg24_26']
selected_pair_covers_all_segments: True
```

这个阶段把 Dream 从普通分段 forward 推进到“选定驻留段 + 批处理服务”的候选路径。

### 6. normal-use candidate

selected-pair service 能稳定处理 48/96 请求，达到“可正常使用的候选服务”：

- 有 systemd candidate service。
- 有 rollback-gated promotion gate。
- 有 normal-use acceptance。

但当时仍不能替换默认服务，因为平均 BPU 和 load/run 还不满足 promotion 目标：

```text
default_service_replaced: False
promotion_decision: block_default_service_replacement
```

### 7. cross-job 摊销 HBM reload

关键突破是 cross-job queue reuse：多个 queue job 在一个 selected-pair resident worker session 内连续处理，使 selected-pair HBM load 不再每个 job 重复完整付费。

candidate service 192 请求遥测：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_candidate_service_telemetry_20260610-182409/service_telemetry_probe.json
processed_request_count: 192
failed_job_count: 0
load_to_run_ratio: 8.66679
avg_bpu_loading: 10.108
amortized_wall_ms_per_processed_request: 1430.794
```

这第一次同时满足三项 default-deploy 性能门槛：

- load/run 低于 9.443895，且低于 9.0。
- avg BPU 高于 8.811，且高于 9.0。
- 长稳态 wall time 不退化。

### 8. 单请求 fallback

cross-job 方案天然偏向多 job 聚合。为了避免低流量时一个请求无限等待，加入了 `--single-job-flush-timeout-sec`，并做了单请求 fallback 验证。

结果：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_selected_pair_cross_job_service_fallback_20260610-185916/cross_job_service_fallback_probe.json
single_job_fallback_ok: True
processed_request_count: 1
failed_job_count: 0
```

注意：单请求 fallback 的延迟约 20.6 秒，说明低流量体验仍不是理想状态。它的价值是“不会卡死”，不是性能优化。

### 9. 默认服务 promotion 与 rollback

最后一步是把 cross-job selected-pair route 从 candidate 提升为默认 Dream 服务。

promotion probe 做了四件事：

1. 把 runtime 发布到稳定路径 `/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default`。
2. 替换 `dream7b-bpu-batch-queue.service`，但保留默认队列 `/mnt/nas/openclaw/queues/dream7b-bpu`。
3. 跑一次默认队列 smoke。
4. 恢复原 unit 验证 rollback，再重新应用 promoted unit。

结果：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_promotion_20260610-190712/cross_job_default_promotion_probe.json
default_service_replaced: True
rollback_verified: True
errors: []
```

### 10. 默认服务长稳态验收

promotion 后，不再只看 candidate 旧报告，而是通过默认队列重新跑 12x16/192 telemetry。

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json
processed_request_count: 192
failed_job_count: 0
queue_done_count: 12
queue_failed_count: 0
load_to_run_ratio: 8.734653
avg_bpu_loading: 9.915
amortized_wall_ms_per_processed_request: 1441.545
```

替换后 deployment acceptance 也通过：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-192303/deployment_acceptance_probe.json
verdict: ok_dream7b_bpu_deployment_acceptance_probe
check_count: 30
passed_check_count: 30
errors: []
```

最终 default-deployable acceptance：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
default_deployable_ready: True
default_deployable_status: ready
blockers: []
warnings: []
```

## 最终架构

```text
client / agent
    |
    v
/mnt/nas/openclaw/queues/dream7b-bpu/pending/*.jsonl
    |
    v
dream7b-bpu-batch-queue.service
    |
    v
/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default/
    |
    v
dream7b_bpu_selected_pair_cross_job_queue_service.py
    |
    v
dream7b_bpu_selected_pair_cross_job_queue_runner.py
    |
    v
selected-pair Dream 7B segmented HBM forward
    |
    v
done / failed + reports + telemetry
```

## 当前可用程度

按工程可用性估计，当前 Dream 7B 部署约为 85% 到 90% 可用。

| 维度 | 估计 | 原因 |
| --- | ---: | --- |
| 默认部署链路 | 95% | 默认服务已替换，systemd active/enabled，rollback 已验证 |
| 长稳态 | 90% | 默认队列 192 请求无失败，deployment acceptance 通过 |
| 性能 | 80% | 三项核心指标达标，但 wall time 仍未到 1400 ms/request |
| 低流量单请求 | 65% | fallback 可用但约 20.6 秒/request，不适合作为理想交互体验 |
| 128TOPS 利用率 | 70%-75% | avg BPU 和 load/run 改善明显，但仍不是 fully saturated |

## 还能优化什么

我们还能继续做的主要是服务层和调度层优化：

1. **动态 flush 策略**  
   根据队列压力自动调整等待时间。低流量时减少等待，高流量时聚合更多 job 摊销 HBM reload。

2. **真实 workload replay**  
   用实际 prompt/token 分布回放，而不是固定 12x16 synthetic jobs，观察真实使用下的吞吐和延迟。

3. **job_count / batch_size sweet spot**  
   系统 sweep `job_count=6/8/10/12`、`request_count=1/4/8/16`，找到默认服务更好的延迟/吞吐折中。

4. **失败 job 隔离和健康检查**  
   增加异常 job quarantine、自动重试、服务健康探针和 telemetry regression gate。

5. **继续 window-cost / resplit 实验**  
   针对 `['seg00_01', 'seg01_02']` 和 `['seg02_04', 'seg04_07']` 继续做分段和加载成本优化。

## 官方工具链团队能做得更好的地方

如果地瓜官方工具链/Runtime 团队介入，他们最可能在底层把性能再拉高：

1. **DreamModel adapter / registry 支持**  
   让 Dream 7B 进入官方 `oellm_build/leap_llm` 白名单，走正式量化、编译、HBM 和 runtime pipeline。

2. **HBM residency 控制**  
   提供 segment 常驻或 persistent cache 能力，从根上减少 reload，而不是像现在这样在服务层摊销 reload。

3. **编译器级 HBM 切分和内存规划**  
   重新规划 section、activation buffer、KV/cache 和算子布局，这比外部手工 resplit 粒度更细。

4. **BPU kernel fusion**  
   对 attention、MLP、RMSNorm、RoPE 等模块做融合和专用 kernel，提升平均 BPU loading。

5. **小 batch / 单请求快路径**  
   当前单请求 fallback 可用但慢。官方如果能提供小 batch runtime fast path，低流量体验会明显改善。

我们能做到的是工程层可部署、可验证、可回滚、可持续优化。要把可用程度从 85%-90% 提到 95% 以上，需要官方工具链或 runtime 接口支持。

## 对外汇报口径

推荐表述：

> Dream 7B 已经在 S100P 上完成默认服务部署。当前方案在官方 Dream adapter 缺失的情况下，通过 segmented HBM、selected-pair residency 和 cross-job 队列摊销降低 HBM reload 影响，完成了 192 请求默认队列长稳态、promotion、rollback 和文档一致性验收。默认服务 telemetry 显示 `load_to_run_ratio=8.734653`、`avg_bpu_loading=9.915`、`amortized_wall_ms_per_processed_request=1441.545`，达到默认可部署标准。

避免表述：

> Dream 7B 已经吃满 128TOPS。

原因：`max_bpu_loading` 不能单独作为 128TOPS 利用率结论。合规说法应强调平均 BPU loading、load/run ratio、wall time 和 sustained telemetry 的综合改善。

## 核心文件入口

- `scripts/probes/dream7b_bpu_cross_job_default_promotion_probe.sh`
- `scripts/probes/dream7b_bpu_cross_job_default_service_telemetry_probe.sh`
- `scripts/probes/dream7b_bpu_default_deployable_acceptance_probe.sh`
- `scripts/dream7b_bpu_selected_pair_cross_job_queue_service.py`
- `scripts/dream7b_bpu_selected_pair_cross_job_queue_runner.py`
- `scripts/probes/project_docs_consistency_probe.sh`

## 最终验收路径

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_promotion_20260610-190712/cross_job_default_promotion_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_deployment_acceptance_20260610-192303/deployment_acceptance_probe.json
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
/tmp/project_docs_consistency/summary.json
```
