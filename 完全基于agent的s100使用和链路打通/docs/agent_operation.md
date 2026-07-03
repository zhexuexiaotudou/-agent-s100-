# Agent 操作约定

本文定义 Codex 这类 agent 使用本仓库时的操作边界和证据标准。

## 0. 新会话入口

如果用户刚拿到 S100P，agent 不应直接进入 YOLO 运行步骤。正确路径是：

1. 先阅读仓库根目录的 `README.md`。
2. 再阅读 `docs/01_s100p_bringup.md`，确认烧录、网线连接、Windows 静态 IP、ping 和 SSH 是否完成。
3. 只有在 `<BOARD_IP>` 已确认、SSH 可连通后，才进入 `docs/02_codex_yolo_workflow.md`。
4. 如果用户说“我已经把 repo 喂给 Codex”，agent 应先询问或检查当前阶段，而不是默认所有前置条件都满足。

推荐用户给 Codex 的启动提示词：

```text
请把这个 repo 当作 S100P 上手和 YOLO 跑通的操作手册。先阅读 README、
docs/01_s100p_bringup.md、docs/02_codex_yolo_workflow.md、docs/agent_operation.md
和 skills 目录。请先判断我现在处在哪一步，再继续执行；不要跳过网络和 SSH 验证。
```

## 1. 角色分工

人负责：

- 接线、上电、进入下载模式。
- 在 XBurn 和 RDK Studio 等 GUI 中完成必须的点击。
- 确认是否允许修改 Windows 网卡配置。
- 提供无法自动读取的截图或错误提示。

agent 负责：

- 读取文档和 skill。
- 通过 SSH/PowerShell 执行可自动化检查。
- 生成和运行脚本。
- 解析日志并给出下一步。
- 把新的成功路径和失败路径沉淀回 repo。

## 2. 变量约定

| 变量 | 示例 | 说明 |
| --- | --- | --- |
| `<BOARD_IP>` | `192.168.127.10` | S100P `eth1` 的 IP |
| `<HOST_IP>` | `192.168.127.2` | Windows 直连网卡 IP |
| `<BOARD_USER>` | `sunrise` | 板端 SSH 用户 |
| `<YOLO_WORKDIR>` | `/home/sunrise/yolo_s100p_run` | 板端 YOLO 工作目录 |
| `<RESULT_FILE>` | `render_test_result.jpeg` | 检测结果图 |

默认口令只作为本地实验示例，agent 不应假设所有设备都使用默认口令。

## 3. 推荐 SSH 方式

Windows 主机可以直接用：

```powershell
ssh sunrise@<BOARD_IP>
```

如果重复操作较多，可以配置 SSH alias：

```text
Host s100p
  HostName <BOARD_IP>
  User sunrise
```

之后：

```bash
ssh s100p
scp file.jpg s100p:/home/sunrise/yolo_s100p_run/
```

## 4. 安全边界

agent 不应在未确认的情况下：

- 改 Windows 默认网卡或无线网卡设置。
- 删除板端用户目录中的非本任务文件。
- 杀掉不属于当前任务的长期运行服务。
- 替换系统镜像或模型文件。
- 把默认密码、私有 token 或私有 SSH key 提交进 repo。

## 5. 每次运行必须采集的证据

### 网络链路

```powershell
Test-NetConnection <BOARD_IP> -Port 22
```

期望：

```text
TcpTestSucceeded : True
```

### 板端系统

```bash
cat /etc/os-release | head
uname -a
```

### ROS/TROS

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash
ros2 pkg prefix dnn_node_example
```

期望输出包含：

```text
/opt/tros/humble
```

### YOLO

日志中应出现：

```text
out box size
Draw result to file: render_feedback_0_0.jpeg
```

结果文件应存在：

```bash
ls -l /home/sunrise/yolo_s100p_run/render_feedback_0_0.jpeg
```

## 6. Handoff 格式

agent 完成一次操作后，建议用这个格式交接：

```text
板端 IP：
执行命令：
关键日志：
结果文件：
浏览器 URL：
残留服务：
后续建议：
```

这样下一轮 agent 可以直接接续，不需要重新探索。
