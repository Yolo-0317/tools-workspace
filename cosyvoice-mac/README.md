# cosyvoice-mac

在 **macOS（Apple Silicon / Intel）** 上最小部署 [CosyVoice 3](https://github.com/FunAudioLLM/CosyVoice)，用于**固定故事库**离线批量生成儿童故事语音。

## 前置条件

| 项目 | 要求 |
|------|------|
| 系统 | macOS 12+ |
| 芯片 | Apple Silicon（M1/M2/M3/M4）或 Intel |
| 内存 | **16GB+** 推荐 |
| 磁盘 | **~5GB**（模型约 2GB + 依赖） |
| 工具 | `git`、`conda`（Miniconda/Anaconda） |
| Python | **3.10**（由 install 脚本创建，勿用系统 3.9） |

> **设备说明**：macOS 上官方路径以 **CPU** 为主（稳定）。MPS 有实验性支持但不保证更快；首次合成约 30s 预热，M 系列 RTF 通常 0.3–0.5。

## 一键安装

```bash
cd cosyvoice-mac
bash scripts/install.sh
```

脚本会：

1. 克隆 `FunAudioLLM/CosyVoice` 到 `vendor/CosyVoice`（含 Matcha-TTS 子模块）
2. 创建 conda 环境 `cosyvoice`（Python 3.10）
3. 安装 macOS 版 PyTorch 与依赖（自动跳过 Linux CUDA 包）
4. 从 HuggingFace 下载 `Fun-CosyVoice3-0.5B-2512`
5. 生成 `.env` 与 `outputs/` 目录

## 验证

```bash
conda activate cosyvoice
cd cosyvoice-mac
python scripts/verify.py
```

## 生成故事语音

### 单篇试音

```bash
conda activate cosyvoice
python scripts/tts_story.py \
  --text-file stories/sample_story.txt \
  --out outputs/sample.wav
```

### 批量固定故事库

把 `.txt` 放进 `stories/`，一键出 mp3/wav：

```bash
python scripts/tts_story.py --batch stories/ --out-dir outputs/
```

### 调整讲故事语气（instruct）

编辑 `.env` 中的 `COSYVOICE_STORY_INSTRUCT`，例如：

```text
You are a gentle storyteller for children. 请用温柔、缓慢、亲切的语气讲睡前故事。<|endofprompt|>
```

或用命令行覆盖：

```bash
python scripts/tts_story.py \
  --text "小狐狸说：今天我们去探险吧！" \
  --instruct "You are a lively storyteller. 请用活泼、略带夸张的语气讲童话。<|endofprompt|>" \
  --out outputs/fox.wav
```

### 克隆参考音色（zero-shot）

换 `--mode zero_shot`，并把 `COSYVOICE_PROMPT_WAV` 指向你自己的 **3–10 秒** 干净人声 wav（背景安静、吐字清晰）。

## 项目结构

```text
cosyvoice-mac/
├── README.md
├── .env.example / .env
├── stories/           # 固定故事文本库（.txt）
├── outputs/           # 生成的 wav（gitignore）
├── pretrained_models/ # 模型权重（gitignore）
├── vendor/CosyVoice/  # 上游仓库（gitignore）
└── scripts/
    ├── install.sh
    ├── download_models.py
    ├── verify.py
    └── tts_story.py
```

## 与 Fish Audio S2 的取舍

| | CosyVoice 3（本项目） | Fish Audio S2 Pro |
|--|----------------------|-----------------|
| 模型大小 | 0.5B | ~4B |
| Mac 本地 | CPU 可稳定跑 | 需 12–24GB 显存，Mac 不现实 |
| 角色语气 | instruct + `[breath]` 等细粒度标签 | `[whisper]` `[excited]` 等标签更丰富 |
| 固定故事库 | 批量生成后只播音频，零运行时负担 | 同 |

若需要 Fish 级别的 inline 情绪标签，可在故事文本里用 CosyVoice 3 支持的标记（见上游 `cosyvoice/tokenizer/tokenizer.py`），例如 `[breath]`；或制作期走 Fish API、播放期仍用本地 mp3。

## 常见问题

### `failed to import ttsfrd, use wetext instead`

正常。`ttsfrd` 仅提供 Linux wheel，Mac 自动回退 `wetext`，不影响讲故事。

### `cannot import name 'cached_download' from 'huggingface_hub'`

```bash
pip install "huggingface_hub<0.26" "diffusers==0.29.0"
```

### 合成很慢

- 首次加载模型约 30s，属正常
- 长故事可拆成多段 txt 分批合成再拼接
- 勿在 macOS 上强开 MPS，多数情况下 **cpu 更稳**

### 重新安装

```bash
rm -rf vendor/CosyVoice pretrained_models
conda env remove -n cosyvoice -y
bash scripts/install.sh
```

## 参考

- 上游仓库：https://github.com/FunAudioLLM/CosyVoice
- 模型卡片：https://huggingface.co/FunAudioLLM/Fun-CosyVoice3-0.5B-2512
- CosyVoice 3 Demo：https://funaudiollm.github.io/cosyvoice3/
