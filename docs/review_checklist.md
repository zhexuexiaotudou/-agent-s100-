# Agent 复审清单

本清单用于定期复审这个仓库，也用于把多个 agent 的分工固定下来。每个 agent 只负责一个视角，最后由主 agent 汇总并修改仓库。

## Agent A：文档可复现性

检查目标：第一次拿到 S100P 的人能否照文档走通。

- README 是否说明仓库目标、适用范围和已验证环境。
- 烧录、联网、RDK Studio、YOLO 四条链路是否连贯。
- 每条命令是否说明执行位置：电脑端、MobaXterm、RDK Studio 终端或 S100P 板端。
- 是否避免把一次实验中的硬编码 IP 当成通用规则。
- 是否说明默认密码只适合本地实验，不应暴露到公网。
- 是否有失败后的下一步检查，而不是只给结论。

输出要求：

- 按严重程度列出问题。
- 给出应修改的文件路径。
- 标注是否影响复现。

## Agent B：脚本可靠性

检查目标：脚本失败时要明确、可诊断、不会误删用户文件。

- PowerShell 脚本是否能解析通过。
- Shell 脚本是否能在板端用 `bash -n` 检查。
- 是否检查依赖命令，例如 `ssh`、`scp`、`ros2`、`python3`。
- 输入文件和输出文件是否可能指向同一个路径。
- 失败时是否返回非零退出码。
- 是否避免宽泛杀进程、递归删除或覆盖已有结果。
- 是否输出日志路径，便于 agent 下一步判断。

输出要求：

- 列出风险点和可能造成的后果。
- 给出推荐修复方向。
- 标注哪些验证已经执行、哪些因为环境不可用未执行。

## Agent C：Skill 可执行性

检查目标：skill 不是说明文，而是能指导 agent 做事的工作流。

- 每个 skill 是否有明确触发条件。
- 是否写明不适用场景，避免 agent 误用。
- 是否列出变量、默认值和可替换项。
- 是否有成功判据。
- 是否有失败恢复路径。
- skill 之间是否能串起来：烧录 -> 联网 -> RDK Studio -> YOLO。
- 是否避免循环前提，例如“需要先连上板子才能知道怎么连板子”。

输出要求：

- 列出每个 skill 的可执行性缺口。
- 给出应补充的变量、检查命令或成功判据。
- 标注是否需要改 README 或 docs 同步。

## 主 Agent 汇总规则

- 先修复会阻断复现的问题。
- 再修复会带来误删、误覆盖、误杀进程的安全问题。
- 最后补充开源协作、排错表和 skill 一致性。
- 修改后至少执行：

```powershell
git diff --check
[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath 'scripts/check_s100p_network.ps1'), [ref]$null) | Out-Null
[System.Management.Automation.PSParser]::Tokenize((Get-Content -Raw -LiteralPath 'scripts/fetch_yolo_result.ps1'), [ref]$null) | Out-Null
```

如果 S100P 在线，还应在板端执行：

```bash
bash -n /home/sunrise/yolo_s100p_run/run_yolo_image.sh
```

并用一张测试图确认输出结果图能通过 HTTP 或 `scp` 取回。
