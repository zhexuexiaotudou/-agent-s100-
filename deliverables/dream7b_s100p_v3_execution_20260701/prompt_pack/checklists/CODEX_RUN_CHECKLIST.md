# Codex 每轮提交检查清单

每个 Codex thread 完成后，检查：

- [ ] 是否没有改动 18888 foreground route？
- [ ] 是否产出 JSON report？
- [ ] 是否产出 Markdown summary？
- [ ] 是否记录输入 case？
- [ ] 是否记录 model/checkpoint/artifact hash？
- [ ] 是否记录脚本路径和运行命令？
- [ ] 是否区分了 pass/fail/blocked/inconclusive/pending？
- [ ] 是否没有把未运行的 gate 写成 failed？
- [ ] 是否没有把 GGUF mismatch 写成 BF16 failure？
- [ ] 是否指出了下一步最小实验？
