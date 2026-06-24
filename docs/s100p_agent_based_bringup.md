# 完全基于 agent 的 S100P 使用和链路打通

## 1. 什么是“用一个 git 开源 repo 管理这些技能”

这里的“技能”不是单纯的一段经验文字，而是 agent 可以反复执行的工作流资产。把它们放进一个 git 开源 repo，意思是用代码仓库的方式管理 S100P 的使用经验、命令、脚本、检查清单和排障记录。

这样做的价值是：

- 可复用：以后换一台电脑或一块新的 S100P，agent 可以直接读取同一套文档和脚本。
- 可迭代：每次踩坑后，把新的判断规则、命令和错误现象补进 repo。
- 可追踪：git commit 能记录每次流程变化，知道某条经验是什么时候、为什么加入的。
- 可协作：其他人可以通过 issue/PR 提交新的板卡、系统版本、网络环境适配经验。
- 可自动化：文档旁边可以放脚本，例如检测 IP、检查 SSH、启动 YOLO、拉取结果图。

一个建议的 repo 结构：

```text
s100p-agent-skills/
├─ README.md
├─ docs/
│  ├─ s100p_agent_based_bringup.md
│  ├─ yolo_detection_workflow.md
│  └─ troubleshooting.md
├─ skills/
│  ├─ s100p_burn_os/
│  │  └─ SKILL.md
│  ├─ s100p_network_link/
│  │  └─ SKILL.md
│  ├─ s100p_rdk_studio/
│  │  └─ SKILL.md
│  └─ s100p_yolo_detection/
│     └─ SKILL.md
├─ scripts/
│  ├─ check_s100p_network.ps1
│  ├─ run_yolo_image.sh
│  └─ fetch_yolo_result.ps1
└─ examples/
   ├─ logs/
   └─ images/
```

其中：

- `docs/` 放人能读懂的完整流程。
- `skills/` 放 agent 能按步骤调用的技能卡。
- `scripts/` 放可执行脚本，减少手敲命令。
- `examples/` 放成功日志、截图、结果图，帮助 agent 判断“什么叫跑通”。

## 2. 背景和目标

目标是形成一条从零开始可复现的 S100P 上手链路：

1. 给 S100P 烧录系统。
2. 通过电脑和板卡直连网络建立 SSH 通路。
3. 在 RDK Studio 添加设备。
4. 用 RDK Studio/SSH 管理板卡。
5. 后续在这个基础上运行 YOLO、查看结果、继续沉淀 agent 技能。

官方参考文档：

- S100 系列烧录教程：https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/install_os/rdk_s100/instruction
- 远程登录与网络说明：https://d-robotics.github.io/rdk_doc/rdk_s/Quick_start/remote_login/

本文件重点记录“官方文档 + 本地实践后跑通的真实路径”。其中网络配置部分以本次实践为准，因为官方入门说明对初学者不够直接。

## 3. 第一步：烧录 S100P 系统

### 3.1 硬件连接

将 S100P 通过 USB Type-C 连接到电脑。

本次实践使用的下载模式：

```text
DFU + Fastboot
```

烧录工具：

```text
XBurn
```

XBurn、驱动和镜像下载链接以官方烧录教程页面为准。

### 3.2 烧录原则

烧录阶段按官方教程执行即可。关键点是：

- 确认电脑能识别进入下载模式的 S100P。
- XBurn 选择正确的 S100 系列镜像。
- 下载模式选择 `DFU + Fastboot`。
- 烧录完成后重启板卡。

烧录阶段不建议 agent 自行发挥，应该严格跟随官方页面。

## 4. 第二步：建立电脑到 S100P 的网络链路

这是本次实践中最关键、也最容易被官方说明误导的一步。

### 4.1 物理连接

用网线连接：

```text
电脑网口 <-> S100P 右侧网口
```

这个右侧网口对应板端的：

```text
eth1
```

### 4.2 获取板端 IP

使用烧录阶段已经用到的 MobaXterm 连接 S100P。

连接成功后在板端执行：

```bash
ifconfig -a
```

找到 `eth1`，记录它后面的 IP 地址。

本次实践中常用的板端 IP 是：

```text
192.168.127.10
```

如果你的板端显示不是这个地址，以 `ifconfig -a` 看到的地址为准。

### 4.3 配置 Windows 电脑网口

打开 Windows：

```text
控制面板
-> 网络和 Internet
-> 网络和共享中心
-> 更改适配器设置
```

找到“以太网连接了一个未知设备”的网卡。这个通常就是连接 S100P 的网卡。

右键：

```text
属性
-> Internet 协议版本 4（TCP/IPv4）
-> 使用下面的 IP 地址
```

填写：

```text
IP 地址：192.168.127.2
子网掩码：255.255.255.0
默认网关：留空
DNS：留空
```

说明：

- 电脑 IP 不要和板端 IP 相同。
- 只要在同一网段即可，例如板端是 `192.168.127.10`，电脑可以是 `192.168.127.2`。
- 默认网关和 DNS 留空，因为这是电脑和板卡之间的直连开发链路，不是用来让板卡上外网。

### 4.4 测试连通性

在 Windows 的 CMD 或 PowerShell 中执行：

```powershell
ping 192.168.127.10
```

这里的 `192.168.127.10` 替换成你在 `eth1` 上看到的板端 IP。

如果有回复，说明电脑和 S100P 网络已经打通。

也可以测试 SSH 端口：

```powershell
Test-NetConnection 192.168.127.10 -Port 22
```

返回 `TcpTestSucceeded : True` 说明 SSH 端口可达。

## 5. 第三步：在 RDK Studio 添加设备

打开 RDK Studio，添加新设备。

连接方式选择：

```text
SSH 网络连接
```

填写板端 IP：

```text
192.168.127.10
```

账号密码通常为：

```text
用户名：sunrise
密码：sunrise
```

如果需要 root：

```text
用户名：root
密码：root
```

连接成功后，RDK Studio 左侧会显示设备在线。之后可以使用：

- 终端
- 文件
- 远程桌面
- 代码编辑
- 烧录相关功能

## 6. 第四步：远程桌面经验

RDK Studio 的远程桌面页本质上依赖 VNC/x11vnc。

页面中默认提示：

```text
VNC 画面口令：88888888
端口：5900
```

如果页面提示 `端口 5900 未就绪`，应检查板端是否已经启动图形桌面和 x11vnc。

可用检查命令：

```bash
ps aux | grep x11vnc
ss -lntp | grep 5900
```

本次实践中，稳定可用的做法是让 `x11vnc` 共享当前 X11 桌面 `:0`，并监听 `5900` 端口。

如果使用 systemd 用户服务，可检查：

```bash
systemctl --user status x11vnc-s100p.service
```

重启：

```bash
systemctl --user restart x11vnc-s100p.service
```

## 7. 第五步：后续运行 YOLO 的基础环境

完成上面的网络和 RDK Studio 链路后，agent 就可以继续做模型推理任务。

本次实践中已经跑通的 YOLO 基础路线是：

```bash
source /opt/ros/humble/setup.bash
source /opt/tros/humble/setup.bash

cd ~/yolo_s100p_run
ros2 launch dnn_node_example dnn_node_example_feedback.launch.py \
  dnn_example_config_file:=config/yolov8workconfig.json \
  dnn_example_image:=test.jpg
```

结果图会生成在当前目录：

```text
render_feedback_0_0.jpeg
```

为了通过浏览器查看结果，可以在结果目录启动临时 HTTP 服务：

```bash
cd ~/yolo_s100p_run
python3 -m http.server 9000 --bind 0.0.0.0
```

然后在电脑浏览器打开：

```text
http://192.168.127.10:9000/render_feedback_0_0.jpeg
```

如果复制成新的结果名，例如：

```text
render_test2_result.jpeg
```

则打开：

```text
http://192.168.127.10:9000/render_test2_result.jpeg
```

## 8. Agent 应该掌握的判断规则

### 8.1 烧录阶段

如果板子没有系统或系统不可用，先回到官方烧录流程，不要直接调 ROS 或 RDK Studio。

### 8.2 网络阶段

如果 RDK Studio 连不上，优先检查：

1. 网线是否接到 S100P 右侧网口。
2. `ifconfig -a` 中 `eth1` 是否有 IP。
3. Windows 以太网 IPv4 是否设置到同一网段。
4. `ping <板端IP>` 是否有回复。
5. `Test-NetConnection <板端IP> -Port 22` 是否成功。

### 8.3 RDK Studio 阶段

如果 SSH 能通但 Studio 添加失败，优先检查：

1. Studio 里是否选择了 `SSH 网络连接`。
2. IP 是否填的是 `eth1` 的 IP。
3. 用户名密码是否为 `sunrise/sunrise`。
4. 是否误用了 USB 虚拟网卡、Wi-Fi 或其他网段地址。

### 8.4 YOLO 阶段

如果 YOLO 没有结果图，检查：

1. 是否执行了 ROS 环境：

   ```bash
   source /opt/ros/humble/setup.bash
   source /opt/tros/humble/setup.bash
   ```

2. 输入图片路径是否存在。
3. 配置文件是否存在：

   ```text
   config/yolov8workconfig.json
   ```

4. 模型文件是否存在：

   ```text
   /opt/hobot/model/s100/basic/yolov8_640x640_nv12.hbm
   ```

5. 日志里是否出现：

   ```text
   Draw result to file: render_feedback_0_0.jpeg
   ```

## 9. 本次沉淀出的核心通路

最终跑通路径可以压缩成一句话：

```text
USB Type-C + XBurn 以 DFU+Fastboot 烧录系统，
再用网线连接电脑和 S100P 右侧 eth1 网口，
通过 MobaXterm 查询 eth1 IP，
把 Windows 以太网 IPv4 配到 192.168.127.x 同网段，
ping 通后在 RDK Studio 中用 SSH 网络连接添加设备，
随后通过 SSH/RDK Studio 执行 ROS2 + TogetheROS.Bot 的 YOLO 推理。
```

这条路径是后续构建“S100P agent 技能库”的基础。

## 10. 下一步建议

建议把本流程拆成 4 个可调用 agent skill：

1. `s100p_burn_os`：烧录系统、下载模式、XBurn 检查。
2. `s100p_network_link`：eth1 直连、Windows 静态 IP、ping/SSH 检查。
3. `s100p_rdk_studio`：Studio 添加设备、远程桌面、文件与终端使用。
4. `s100p_yolo_detection`：上传图片、运行 YOLO、生成结果图、通过 HTTP 查看。

每个 skill 都应该包含：

- 触发条件
- 前置条件
- 具体命令
- 成功判据
- 常见失败现象
- 修复动作

这样就能把“我这次手工跑通的经验”升级成“agent 可复用的 S100P 上手能力”。
