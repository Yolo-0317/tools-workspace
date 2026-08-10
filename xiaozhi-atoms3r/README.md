# xiaozhi-atoms3r

在 **Cursor / VS Code** 中开发 **M5Stack AtomS3R CAM 或 AtomS3R M12 + Atomic Echo Base** 的小智 AI 语音固件。

硬件组合：

| 部件 | 说明 |
|------|------|
| AtomS3R CAM | 0.3MP GC0308 摄像头，ESP32-S3-PICO-1-N8R8 |
| AtomS3R M12 | 3MP OV3660 广角摄像头，同 SoC |
| Atomic Echo Base | ES8311 音频编解码 + MEMS 麦克风 + 8Ω 扬声器 |

两款主控 **均无屏幕、无独立按键**，需语音唤醒；调试时建议开串口 monitor 看日志。

上游固真源：[78/xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) · 板型目录 `main/boards/atoms3r-cam-m12-echo-base` · 百科 [飞书](https://my.feishu.cn/wiki/F5krwD16viZoF0kKkvDcrZNYnhb) / [xiaozhi.me/docs](https://xiaozhi.me/docs)

## 前置条件

| 项目 | 要求 |
|------|------|
| 系统 | macOS（Apple Silicon / Intel）或 Linux |
| 工具 | `git`、`python3`（3.10+） |
| 磁盘 | ESP-IDF 工具链约 **2–3 GB**；固件源码约 **500 MB** |
| 硬件 | USB-C 数据线；Echo Base 已堆叠在 Atom 主控上 |

> 首次使用可跳过本仓库，直接用 [M5Burner](https://docs.m5stack.com/en/uiflow/m5burner/intro) 烧录预编译小智固件；本仓库面向 **改源码、二次开发**。

## 一键初始化

在 Cursor 中打开 **`xiaozhi-atoms3r/`** 文件夹（或整个 monorepo，脚本路径相对本目录）：

```bash
cd xiaozhi-atoms3r

# 1. 拉取小智固件源码 -> firmware/
bash scripts/setup.sh

# 2. 安装 ESP-IDF v6.0.2 + esp32s3 工具链 -> .espressif/
bash scripts/install-idf.sh

# 3. 复制环境变量（install-idf 已生成 .env，可选手动改串口）
cp -n .env.example .env
```

`install-idf.sh` 首次运行约 **10–20 分钟**（下载编译器与 Python 虚拟环境）。

## Cursor / VS Code 配置

1. 安装扩展：**Espressif IDF**（`espressif.esp-idf-extension`）— 打开本目录时 Cursor 会提示安装。
2. 已预置 `.vscode/settings.json`：
   - `idf.espIdfPath` → `.espressif/esp-idf-v6.0.2`
   - `idf.toolsPath` → `.espressif/tools`
3. **重要**：ESP-IDF 扩展的「项目根」应指向 **`firmware/`**（xiaozhi-esp32 仓库根）。在扩展命令面板执行 `ESP-IDF: Set Espressif Device Target` → `esp32s3`，再 `ESP-IDF: SDK Configuration editor (menuconfig)`：
   - `Xiaozhi Assistant` → `Board Type` → **AtomS3R CAM/M12 + Echo Base**
   - `Xiaozhi Assistant` → `IoT Protocol` → **MCP 协议**（启用摄像头视觉）
   - `Partition Table` → Custom partition → `partitions/v2/8m.csv`
   - `Serial flasher config` → Flash size → **8 MB**

## 编译与烧录

### 推荐：release 脚本（自动选板型）

```bash
bash scripts/build.sh
```

内部执行 `python3 firmware/scripts/release.py atoms3r-cam-m12-echo-base`。

### 烧录

1. USB 连接设备
2. **按住 RESET 约 2 秒**，直到绿灯亮，进入下载模式
3. 若自动识别失败，在 `.env` 设置 `ESPPORT=/dev/cu.usbmodemXXXX`

```bash
bash scripts/flash.sh
bash scripts/monitor.sh   # 查看日志 / 验证码
```

### 开发迭代

```bash
bash scripts/dev.sh   # menuconfig -> build -> flash -> monitor
```

## 配网与账号

1. 烧录后设备会播报或在串口输出 **6 位验证码**
2. 手机连接设备热点或按语音引导配置 Wi-Fi
3. 登录 [xiaozhi.me](https://xiaozhi.me) 控制台绑定设备（个人可免费使用 Qwen 实时模型）
4. 唤醒词：**「你好小智」**（CAM/M12 专用固件 v1.6.2+）

详见飞书：[配置 Wi-Fi 和登记设备](https://my.feishu.cn/wiki/F5krwD16viZoF0kKkvDcrZNYnhb)

## 目录结构

```text
xiaozhi-atoms3r/
├── .env.example          # IDF 路径、板型、串口
├── .vscode/              # ESP-IDF 扩展配置
├── scripts/
│   ├── install-idf.sh    # 安装 ESP-IDF v6.0.2
│   ├── setup.sh          # clone xiaozhi-esp32
│   ├── build.sh          # release.py 编译
│   ├── flash.sh / monitor.sh / dev.sh
│   └── common.sh
├── firmware/             # 78/xiaozhi-esp32（git clone，不入库）
└── .espressif/           # IDF + 工具链（不入库）
```

## 硬件引脚速查（Echo Base + CAM/M12）

| 功能 | GPIO |
|------|------|
| I2S WS | G6 |
| I2S BCLK | G8 |
| I2S DIN (mic) | G7 |
| I2S DOUT (spk) | G5 |
| I2C SDA / SCL (ES8311) | G38 / G39 |
| BOOT 键 | G41 |
| 摄像头 | 见 `firmware/main/boards/atoms3r-cam-m12-echo-base/config.h` |

M5 官方文档：[AtomS3R-CAM AI Chatbot](https://docs.m5stack.com/en/core/AtomS3R-CAM%20AI%20Chatbot) · [Echo Base 小智教程](https://docs.m5stack.com/en/guide/realtime/xiaozhi/atomic_echo_base)

## 常见问题

**编译报 IDF 版本不对**  
小智 main 分支要求 **ESP-IDF v6.0+**（推荐 v6.0.2）。勿用 v5.x，除非刷旧版固件 tag。

**无屏幕如何知道状态**  
必须 `bash scripts/monitor.sh` 或 M5Burner 串口工具；配网验证码在日志里。

**CAM 与 M12 选哪个板型**  
upstream 用 **同一板型** `atoms3r-cam-m12-echo-base`；摄像头驱动在运行时按传感器自动适配。

**只想快速体验、不改代码**  
M5Burner → 搜索「XiaoZhi Voice Assistant」→ 选 **AtomS3R-CAM / AtomS3R-M12** 版本固件 Web 烧录。

## 相关链接

- [xiaozhi-esp32 GitHub](https://github.com/78/xiaozhi-esp32)
- [自定义开发板指南](https://github.com/78/xiaozhi-esp32/blob/main/docs/custom-board_zh.md)
- [MCP 物联网控制](https://github.com/78/xiaozhi-esp32/blob/main/docs/mcp-usage_zh.md)
