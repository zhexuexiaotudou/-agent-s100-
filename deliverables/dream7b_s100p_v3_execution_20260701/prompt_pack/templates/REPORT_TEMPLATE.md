# Report Template

## Metadata

```json
{
  "report_name": "",
  "created_at": "",
  "script_version": "",
  "git_commit": "",
  "host": "",
  "device": "",
  "model_path": "",
  "checkpoint_hash": "",
  "artifact_hash": "",
  "cases": []
}
```

## Hypothesis

写明本轮实验要验证的假设。

## Method

写明输入、命令、脚本、环境。

## Results

列出关键指标。

## Gate Verdict

```text
gate_name:
status: pass/fail/blocked/inconclusive/pending
reason:
blocking_issue:
```

## Evidence

列出 artifact 路径和字段名。

## Boundary

写明本结论不能推出什么。

## Next Minimal Experiment

只写下一步最小实验，不要泛泛建议。
