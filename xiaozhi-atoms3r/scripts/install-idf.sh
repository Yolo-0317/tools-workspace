#!/usr/bin/env bash
# 安装 ESP-IDF v6.0.2 到 xiaozhi-atoms3r/.espressif/（与 upstream 小智 v2.x 要求一致）
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IDF_VERSION="v6.0.2"
IDF_DIR="$ROOT/.espressif/esp-idf-v6.0.2"
TOOLS_DIR="$ROOT/.espressif/tools"
GITEE_TOOLS_DIR="$ROOT/.espressif/esp-gitee-tools"

# 国内网络默认走 Gitee + 乐鑫 CDN；可 USE_CN_MIRROR=0 强制 GitHub
: "${USE_CN_MIRROR:=1}"

mkdir -p "$ROOT/.espressif"

if [[ -f "$IDF_DIR/export.sh" ]]; then
  echo "ESP-IDF already present: $IDF_DIR"
  exit 0
fi

GIT_NET=( -c http.version=HTTP/1.1 -c http.postBuffer=524288000 )

clone_idf_github() {
  local attempt
  for attempt in 1 2 3; do
    rm -rf "$IDF_DIR"
    echo "Cloning ESP-IDF $IDF_VERSION from GitHub (attempt $attempt/3)"
    if git "${GIT_NET[@]}" clone --depth 1 --branch "$IDF_VERSION" \
      https://github.com/espressif/esp-idf.git "$IDF_DIR"; then
      return 0
    fi
    echo "GitHub clone failed, retrying in 10s..." >&2
    sleep 10
  done
  return 1
}

update_submodules_github() {
  local attempt
  cd "$IDF_DIR"
  for attempt in 1 2 3; do
    echo "Updating submodules from GitHub (attempt $attempt/3)..."
    if git "${GIT_NET[@]}" submodule update --init --depth 1 --recursive; then
      return 0
    fi
    echo "Submodule update failed, retrying in 10s..." >&2
    sleep 10
  done
  return 1
}

clone_idf_gitee() {
  rm -rf "$IDF_DIR"
  echo "Cloning ESP-IDF $IDF_VERSION from Gitee (no submodules yet)"
  git "${GIT_NET[@]}" clone --depth 1 --branch "$IDF_VERSION" \
    https://gitee.com/EspressifSystems/esp-idf.git "$IDF_DIR"
}

update_submodules_gitee() {
  if [[ ! -d "$GITEE_TOOLS_DIR/.git" ]]; then
    echo "Cloning esp-gitee-tools"
    git "${GIT_NET[@]}" clone --depth 1 \
      https://gitee.com/EspressifSystems/esp-gitee-tools.git "$GITEE_TOOLS_DIR"
  fi
  echo "Updating submodules via esp-gitee-tools (Gitee/Jihu mirrors)"
  bash "$GITEE_TOOLS_DIR/submodule-update.sh" "$IDF_DIR"
}

if [[ "$USE_CN_MIRROR" == "1" ]]; then
  clone_idf_gitee
  update_submodules_gitee
else
  clone_idf_github
  update_submodules_github
fi

echo "Installing ESP-IDF tools (may take 10-20 minutes)..."
export IDF_TOOLS_PATH="$TOOLS_DIR"
if [[ "$USE_CN_MIRROR" == "1" ]]; then
  export IDF_GITHUB_ASSETS="${IDF_GITHUB_ASSETS:-dl.espressif.cn/github_assets}"
  export PIP_INDEX_URL="${PIP_INDEX_URL:-https://mirrors.tuna.tsinghua.edu.cn/pypi/web/simple}"
  echo "Using CN mirror: IDF_GITHUB_ASSETS=$IDF_GITHUB_ASSETS"
fi

cd "$IDF_DIR"
./install.sh esp32s3

cat > "$ROOT/.env" <<EOF
IDF_PATH=$IDF_DIR
XIAOZHI_FIRMWARE_DIR=firmware
XIAOZHI_BOARD=atoms3r-cam-m12-echo-base
ESPPORT=
USE_CN_MIRROR=$USE_CN_MIRROR
EOF

echo
echo "Done. Next:"
echo "  bash scripts/build.sh"
