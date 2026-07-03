# Package Contents

- `GPT_PRO_REVIEW_PROMPT.md`: 上传给 GPT Pro 后可直接粘贴的复核提示词。
- `GPT_PRO_REVIEW_README.md`: 本包结构、结论边界和关键证据说明。
- `01_final_evidence/`: 最终 gate packet、别名 packet、中文技术报告。
- `reports/`: 所有 gate、diagnostic、inventory 的 JSON/MD 报告。
- `tools/`: 本轮执行和复核用脚本。
- `scripts/`: 既有 evidence package 复核脚本。
- `cases/`: seq128 probe battery 和 boundary case 列表。
- `prompt_pack/`: 用户提供的原始提示词包展开内容。
- `evidence/bf16_reference_probe/`: BF16 reference exporter 的 blocked 记录。
- `evidence/codex_dream7b_s100p_evidence_metadata_20260701.tgz`: 板端 evidence/reports/cases 元数据包，已排除 `.npy/.bin` 大数组。

原始大数组未放入紧凑 zip；请使用 `reports/100_raw_evidence_inventory.json` 中的路径、大小和 SHA256 复核其存在性。
