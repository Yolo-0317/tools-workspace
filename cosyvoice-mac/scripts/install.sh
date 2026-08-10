#!/usr/bin/env bash
# CosyVoice 3 最小安装 — macOS Apple Silicon / Intel
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENDOR="$ROOT/vendor/CosyVoice"
ENV_NAME="${COSYVOICE_CONDA_ENV:-cosyvoice}"
PYTHON_VERSION="${COSYVOICE_PYTHON:-3.10}"

echo "==> cosyvoice-mac 安装"
echo "    项目目录: $ROOT"

if ! command -v conda >/dev/null 2>&1; then
  echo "错误: 未找到 conda。请先安装 Miniconda: https://docs.conda.io/en/latest/miniconda.html"
  exit 1
fi

# 1. 克隆上游仓库（含 Matcha-TTS 子模块）
if [[ ! -d "$VENDOR/.git" ]]; then
  echo "==> 克隆 FunAudioLLM/CosyVoice ..."
  mkdir -p "$ROOT/vendor"
  git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git "$VENDOR"
else
  echo "==> 已存在 $VENDOR，跳过 clone"
fi

if [[ ! -f "$VENDOR/third_party/Matcha-TTS/setup.py" ]]; then
  echo "==> 初始化子模块 Matcha-TTS ..."
  (cd "$VENDOR" && git submodule update --init --recursive)
fi

# 2. Conda 环境
if ! conda env list | awk '{print $1}' | grep -qx "$ENV_NAME"; then
  echo "==> 创建 conda 环境: $ENV_NAME (python=$PYTHON_VERSION)"
  conda create -n "$ENV_NAME" -y "python=$PYTHON_VERSION"
fi

# shellcheck disable=SC1091
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$ENV_NAME"

echo "==> Python: $(which python) ($(python -V))"

# 3. PyTorch（macOS 标准 wheel，勿用 cu121 索引）
echo "==> 安装 PyTorch (macOS) ..."
pip install --upgrade pip
pip install "torch==2.3.1" "torchaudio==2.3.1"

# 4. 其余依赖（过滤 CUDA 索引行，避免误装 GPU 包）
echo "==> 安装 CosyVoice 依赖 ..."
REQ_TMP="$(mktemp)"
grep -v '^--extra-index-url' "$VENDOR/requirements.txt" \
  | grep -v '^torch==' \
  | grep -v '^torchaudio==' > "$REQ_TMP"
pip install -r "$REQ_TMP"
rm -f "$REQ_TMP"

# 5. 下载模型（约 2GB）
echo "==> 下载 Fun-CosyVoice3-0.5B-2512 ..."
python "$ROOT/scripts/download_models.py"

# 6. 环境文件
if [[ ! -f "$ROOT/.env" ]]; then
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo "==> 已创建 .env（可按需修改）"
fi

mkdir -p "$ROOT/outputs" "$ROOT/stories"

echo ""
echo "安装完成。"
echo "  conda activate $ENV_NAME"
echo "  cd $ROOT"
echo "  python scripts/verify.py"
echo "  python scripts/tts_story.py --text \"你好，这是一个测试。\" --out outputs/test.wav"
