# Dream 7B 在 S100P 上的部署优化汇报

报告日期：2026-06-10  
项目仓库：https://github.com/zhexuexiaotudou/-agent-s100-  
Repo 专题入口：`docs/dream7b_s100p_deployment_optimization/README.md`  
本地路径：`F:\Project\Digua\完全基于agent的s100使用和链路打通\docs\dream7b_s100p_deployment_optimization\README.md`

## 一句话结论

Dream 7B 已经从“官方没有现成参考、不能直接走官方白名单工具链”的状态，推进到 S100P 默认队列服务可部署状态。当前默认服务已替换为 cross-job selected-pair 路线，完成 192 请求长稳态遥测、默认服务 promotion、rollback 验证和最终 acceptance，具备作为项目亮点汇报的工程闭环。

这不是“跑通一次 demo”。核心价值在于：在官方 Dream adapter 缺失的条件下，我们建立了可复现、可服务化、可回滚、可验收的替代部署路线，并用 telemetry 证明它相比早期分段 HBM 路线有实质优化。

## 当前交付状态

| 项目 | 当前状态 |
| --- | --- |
| 默认服务 | `dream7b-bpu-batch-queue.service` |
| 默认队列 | `/mnt/nas/openclaw/queues/dream7b-bpu` |
| 稳定 runtime | `/mnt/nas/openclaw/runtimes/dream7b-bpu-cross-job-default` |
| 默认部署结论 | `default_deployable_ready: True` |
| rollback | 已验证 |
| blockers | 无 |
| warnings | 无 |

最终验收报告显示：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
default_deployable_ready: True
default_deployable_status: ready
blockers: []
warnings: []
```

## 核心指标

最终默认服务 192 请求遥测结果如下：

| 指标 | 结果 | 汇报含义 |
| --- | ---: | --- |
| processed_request_count | 192 | 默认队列完成 12 个 job，每个 job 16 请求 |
| failed_job_count | 0 | 长稳态无失败 job |
| queue_done_count | 12 | 默认队列完成数正常 |
| queue_failed_count | 0 | 默认队列无失败文件 |
| load_to_run_ratio | 8.734653 | 低于 9.0 目标，reload 摊销有效 |
| avg_bpu_loading | 9.915 | 高于 9.0，平均 BPU 利用率有实质改善 |
| max_bpu_loading | 98.0 | 仅作辅助观察，不作为 128TOPS 成功口径 |
| amortized_wall_ms_per_processed_request | 1441.545 ms | 低于 96 请求长稳退化边界 |

对外表述建议：Dream 7B 当前已经达到 S100P 默认可部署标准，并且在 sustained telemetry 中体现出 load/run ratio、平均 BPU loading 和摊销 wall time 的综合改善。不要表述为“已经吃满 128TOPS”，因为 max BPU loading 不能单独支撑这个结论。

## 技术路线的关键价值

老师给出的建议是先跑官方 SDK 已支持 LLM 的“源模型到部署”全流程，再换 Dream 7B 复用同一套检查。这个路线已经完成了关键闭环：

1. 用 Qwen2.5-1.5B 建立官方 LLM baseline。
2. 迁移到 Dream 7B 时确认官方 `oellm_build/leap_llm` 路线阻塞在 registry/model adapter。
3. 将“编译失败”归因为可沟通的 SDK 适配缺口，而不是环境问题。
4. 继续走 segmented HBM 路线，让真实 Dream 7B 权重进入 S100P BPU 执行路径。
5. 通过 selected-pair residency 和 cross-job queue reuse 摊销 HBM reload。
6. 最终把 candidate route 提升为默认服务，并验证 rollback。

因此，这条成果的亮点不是单点性能数字，而是把一个官方无参考模型推进成了工程可部署路线。

## 主要卡点与处理结果

| 卡点 | 判断 | 处理结果 |
| --- | --- | --- |
| 官方 Dream 7B `oellm_build` 路线 | SDK registry 中无 DreamModel adapter | 已形成最小失败包，可给老师或厂商确认 |
| 官方 Qwen 1024/256 | S100P common-buffer/BPU 内存分配失败 | 降到 512/128 后作为官方 runnable baseline |
| 官方 DeepSeek 7B HBM | 当前 S100P 内存布局下仍 common-buffer blocked | 不能作为当前可靠兜底 |
| Dream segmented HBM 早期路线 | 能跑 BPU，但 HBM reload dominated | 转向 selected-pair 与 cross-job 摊销 |
| selected-pair candidate | 墙钟时间改善，但早期平均 BPU 不稳定 | 增加 sustained telemetry 和 promotion gate |
| cross-job route | 高负载有效，但低流量可能等待 | 加入 single-job fallback，保证不会卡死 |

其中最重要的结论是：Dream 7B 官方路线卡点已经明确为 SDK adapter 缺失；当前可交付路线不是官方完整编译路线，而是经过验证的 segmented HBM + service-level runtime 路线。

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
done / failed + telemetry reports
```

## 为什么能算项目亮点

第一，目标难度高。Dream 7B 不在官方现成示例中，直接复用官方 LLM 白名单路线不可行。

第二，卡点被工程化定位。我们没有停在“编译失败”或“内存不够”，而是区分了官方 Qwen common-buffer 失败、Dream registry 缺失、DeepSeek 7B HBM 过大和 Dream 自身 HBM reload dominated 这几类不同问题。

第三，路线可复现。每个关键节点都有 probe、report、service、runtime 路径和 acceptance gate，不依赖一次手工运行。

第四，最终进入默认服务。当前不是候选服务停留在旁路，而是已经替换默认 Dream 队列服务，并验证 rollback。

第五，性能口径克制。报告不以 `max_bpu_loading=98.0` 宣称吃满 128TOPS，而是以平均 BPU、load/run ratio、192 请求 sustained telemetry 和 wall time 综合判断。

## 当前可用程度

按工程可用性估计，当前 Dream 7B 部署约为 85% 到 90% 可用。

| 维度 | 估计 | 依据 |
| --- | ---: | --- |
| 默认部署链路 | 95% | 默认服务已替换，rollback 已验证 |
| 长稳态 | 90% | 192 请求默认队列无失败，acceptance 通过 |
| 性能 | 80% | 三项核心指标达标，但仍有 reload 开销 |
| 低流量单请求 | 65% | fallback 可用，但低流量延迟仍偏高 |
| 128TOPS 利用率 | 70%-75% | 平均 BPU 有改善，但还不是 full saturation |

结论：Dream 7B 已经可以作为 S100P 上的默认可部署模型路线继续打磨；如果追求交互级低延迟和更高平均 BPU 利用率，还需要进一步优化 service flush、runtime residency 和官方工具链接口。

## 仍需继续优化的方向

短期由我们继续推进：

- 动态 flush 策略：根据队列压力自动调整单请求等待和多 job 聚合。
- 真实 workload replay：用实际 prompt/token 分布替代固定 synthetic jobs。
- batch/job sweet spot：系统扫描 job_count、request_count、flush timeout 的延迟吞吐折中。
- 健康检查和异常隔离：增加 failed job quarantine、自动重试和 telemetry regression gate。
- window-cost 继续优化：针对高 reload window 继续做切分与调度实验。

需要老师或厂商支持：

- DreamModel 官方 adapter：让 Dream 7B 进入 `oellm_build/leap_llm` 正式白名单。
- HBM residency / persistent cache 接口：从 runtime 层减少 reload，而不是只在 service 层摊销。
- 编译器级 HBM section 规划：比外部手工 segment split 更细粒度。
- 小 batch / 单请求快路径：改善低流量交互体验。
- 7B 官方 HBM 内存布局建议：确认 S100P 当前 common-buffer 限制下官方 7B 模型的推荐配置。

## 可引用证据入口

默认服务 promotion：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_promotion_20260610-190712/cross_job_default_promotion_probe.json
default_service_replaced: True
rollback_verified: True
errors: []
```

默认服务 192 请求 telemetry：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_cross_job_default_service_telemetry_20260610-191115/default_service_telemetry_probe.json
processed_request_count: 192
failed_job_count: 0
load_to_run_ratio: 8.734653
avg_bpu_loading: 9.915
amortized_wall_ms_per_processed_request: 1441.545
```

最终 default-deployable acceptance：

```text
/mnt/nas/openclaw/reports/models/dream7b_bpu_default_deployable_acceptance_20260610-192303/default_deployable_acceptance_probe.json
default_deployable_ready: True
default_deployable_status: ready
```

Dream 官方路线阻塞：

```text
/mnt/nas/openclaw/reports/models/dream7b_oellm_fullflow_feasibility_20260609-223754/dream7b_oellm_fullflow_feasibility_probe.json
dream_registered_in_official_sdk: False
compile_status: blocked_registry_missing
failure_stage: registry_missing
direct_oellm_migration_supported: False
```

## 汇报建议

建议主标题：**无官方参考模型到默认服务：Dream 7B 在 S100P 上的分段 HBM 部署优化**

建议汇报重点：

1. 先说明老师要求的官方基线到 Dream 迁移路线已经执行。
2. 再说明 Dream 官方路线卡点已明确，不是环境问题。
3. 重点展示我们建立的 segmented HBM + selected-pair + cross-job 默认服务路线。
4. 用 192 请求 telemetry 和 rollback 验证证明它不是一次性 demo。
5. 最后说明下一步如果官方工具链支持 Dream adapter 和 HBM residency，性能还有继续上探空间。

