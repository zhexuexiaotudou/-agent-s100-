# Baseline Progress: S100P BPU HBM Smoke

Date: 2026-06-01

This note adds a concrete BPU utilization gate for the S100P + NAS + OpenClaw
baseline. It separates two claims:

- S100P can use its BPU/128 TOPS accelerator path for compiled `.hbm` models.
- The current Dream 7B GGUF deployment is CPU-only and does not use BPU.

## New Probe

```text
script: scripts/probes/bpu_hbm_smoke_probe.sh
remote path: /root/.openclaw/workspace/scripts/probes/bpu_hbm_smoke_probe.sh
default output: /mnt/nas/openclaw/reports/bpu
default model: /opt/hobot/model/s100/basic/resnet18_224x224_nv12.hbm
```

The probe checks and records:

- exposed BPU core count from `/sys/devices/system/bpu/core_num`;
- BPU frequency and governor from `/sys/class/devfreq/28108000.bpu`;
- model metadata from `hrt_model_exec model_info`;
- single-frame inference through `hrt_model_exec infer`;
- throughput/latency through `hrt_model_exec perf`;
- sampled BPU loading through `hrt_ucp_monitor`.

Safety boundary:

- no model download;
- no package install;
- no persistent service start;
- no deletion;
- writes only to approved report directories.

## Board Validation

Latest NAS-backed evidence:

```text
report: /mnt/nas/openclaw/reports/bpu/bpu_hbm_smoke_20260601-132341/summary.md
verdict: ok_bpu_hbm_smoke
model: /opt/hobot/model/s100/basic/resnet18_224x224_nv12.hbm
model name: resnet18_224x224_nv12
model MARCH: nash-e
model CORE_NUM: 1
system BPU cores exposed: 1
BPU frequency: 1500000000 Hz
BPU governor: performance
single-frame infer time: 1.352 ms
perf frame count: 2000
perf threads: 8
average latency: 2.634 ms
frame rate: 3003.833 FPS
max sampled BPU loading: 100.0%
```

This is a real BPU smoke/perf loop, not a CPU benchmark. The evidence logs show
BPULib/DNN runtime loading the `.hbm` model, and `hrt_ucp_monitor` sampled BPU0
at 100% loading during the perf run.

## Dream 7B Boundary

Dream 7B is currently deployed through `diffuse-cpp` with a GGUF model:

```text
model: /mnt/nas/openclaw/models/dream7b/dream-7b-q4km.gguf
runtime: /mnt/nas/openclaw/runtimes/diffuse-cpp
entrypoints: /usr/local/bin/dream7b-cli, /usr/local/bin/dream7b-text
```

That runtime links the CPU ggml backend, so it does not consume the BPU/128 TOPS
accelerator path. Dream should remain labeled as local CPU/DLM capability until
there is an S100-compatible `.hbm` conversion or official S100 LLM toolchain
support for Dream.

## Practical Direction

For the current project, the immediate way to use the 128 TOPS path is to put
vision/perception workloads on S100P BPU:

- image classification or object detection on NAS images;
- OCR detection/recognition using installed PP-OCR `.hbm` models;
- segmentation or scene metadata extraction for OpenClaw/NAS workflows;
- robotics camera inference through the existing `dnn_node`/ROS2 path.

For local LLM acceleration, use an official S100-supported LLM family first
instead of trying to force Dream onto BPU as a short-term task.
