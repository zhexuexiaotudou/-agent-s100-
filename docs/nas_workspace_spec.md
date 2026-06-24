# NAS Workspace 规范

本文定义第一版 OpenClaw + S100P + TS-264C 的专用 NAS workspace。目标是让 OpenClaw 只接触一个最小共享目录，而不是整个 NAS。

## 目标路径

NAS 侧建议创建共享：

```text
/OpenClawWorkspace
```

S100P 侧挂载到：

```text
/mnt/nas/openclaw
```

第一版只允许 OpenClaw、脚本和 agent 写入这个挂载点下的目录。

## 目录结构

```text
/OpenClawWorkspace/
  inbox/
  outbox/
  documents/
  photos/
  videos/
  robot_datasets/
  logs/
    openclaw/
    probes/
    robot/
  reports/
    daily/
    weekly/
    experiments/
  tmp/
```

| 目录 | 用途 | 第一版权限建议 |
| --- | --- | --- |
| `inbox/` | 人手动丢给 agent 处理的输入 | OpenClaw 读写 |
| `outbox/` | agent 生成给人查看的结果 | OpenClaw 读写 |
| `documents/` | 文档、说明书、实验记录源文件 | OpenClaw 只读优先，索引任务可读写索引文件 |
| `photos/` | 图片原始资料 | OpenClaw 只读优先 |
| `videos/` | 视频原始资料 | OpenClaw 只读优先 |
| `robot_datasets/` | ROS bag、传感器快照、数据集 card | S100P 采集脚本读写 |
| `logs/` | OpenClaw、探针、机器人任务日志 | 追加写 |
| `reports/` | 周报、实验报告、诊断报告 | OpenClaw 读写 |
| `tmp/` | 可清理临时文件 | 可写，定期清理 |

## 不进入第一版的范围

- 不挂载 NAS 根目录。
- 不复用 NAS 管理员账号。
- 不让 OpenClaw 写入个人照片库、备份根目录或其他共享。
- 不把 token、API key、SSH key 放入 NAS workspace。

## 验收命令

S100P 板端：

```bash
mount | grep /mnt/nas/openclaw
findmnt /mnt/nas/openclaw
test -d /mnt/nas/openclaw/documents
test -w /mnt/nas/openclaw/logs
touch /mnt/nas/openclaw/tmp/.write_test && rm /mnt/nas/openclaw/tmp/.write_test
```

重启后还需要再次执行同样检查，确认自动挂载仍然存在。

## 初始化脚本

仓库提供：

```bash
scripts/init_nas_workspace.sh /mnt/nas/openclaw
```

这个脚本只创建目录和 README，不负责挂载 NAS。挂载本身需要先确认 TS-264C 的共享协议、地址、账号和权限。
