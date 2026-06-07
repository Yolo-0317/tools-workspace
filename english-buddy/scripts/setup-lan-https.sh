#!/usr/bin/env bash
# 内网手机带读：mkcert 本地证书 + Caddy :8443 HTTPS（麦克风须安全上下文）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
WORKSPACE="$(cd "${ROOT}/.." && pwd)"
SIDESTORE="${WORKSPACE}/sidestore-infra"
ENV_FILE="${ROOT}/.env"
HTTPS_PORT="${INTERNAL_HTTPS_PORT:-8443}"

LAN_IP="${LAN_IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)}"
if [[ -z "$LAN_IP" ]]; then
  echo "无法检测局域网 IP，请: export LAN_IP=192.168.x.x && $0" >&2
  exit 1
fi

ORIGIN="https://${LAN_IP}:${HTTPS_PORT}"

if [[ ! -d "$SIDESTORE" ]]; then
  echo "缺少 sidestore-infra，无法配置 Caddy 反代。" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  cp "${ROOT}/.env.example" "$ENV_FILE"
  echo "已从 .env.example 创建 ${ENV_FILE}"
fi

echo "==> 生成 mkcert 证书并写入 Caddy（LAN ${LAN_IP}）"
LAN_IP="$LAN_IP" INTERNAL_HTTPS_PORT="$HTTPS_PORT" bash "${SIDESTORE}/scripts/mkcert-lan-ip.sh"

python3 - "$ENV_FILE" "$ORIGIN" <<'PY'
import pathlib
import sys

path = pathlib.Path(sys.argv[1])
origin = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
out: list[str] = []
cors_idx = None
for i, line in enumerate(lines):
    if line.startswith("CORS_ORIGINS="):
        cors_idx = i
        val = line.split("=", 1)[1]
        parts = [p.strip() for p in val.split(",") if p.strip()]
        if origin not in parts:
            parts.append(origin)
        out.append("CORS_ORIGINS=" + ",".join(parts))
    else:
        out.append(line)

if cors_idx is None:
    out.append(
        "CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173," + origin
    )

secure_set = False
for i, line in enumerate(out):
    if line.startswith("ENGLISH_BUDDY_COOKIE_SECURE="):
        out[i] = "ENGLISH_BUDDY_COOKIE_SECURE=1"
        secure_set = True
if not secure_set:
    out.append("ENGLISH_BUDDY_COOKIE_SECURE=1")

path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print(f"已更新 {path.name}: CORS + ENGLISH_BUDDY_COOKIE_SECURE=1")
PY

echo "==> 重启 English Buddy"
"${ROOT}/scripts/restart.sh"

echo ""
echo "完成。手机带读请打开："
echo "  ${ORIGIN}/english/"
echo ""
if command -v mkcert >/dev/null 2>&1; then
  CAROOT="$(mkcert -CAROOT)"
  echo "iPhone / iPad 首次须信任 mkcert 根证书（一次性）："
  echo "  1. 把 ${CAROOT}/rootCA.pem 发到手机（AirDrop / 微信文件）"
else
  CERT="${SIDESTORE}/certs/lan-ip/cert.pem"
  echo "未安装 mkcert，当前为 openssl 自签证书。手机须安装并信任："
  echo "  1. 把 ${CERT} 发到手机"
  echo "  建议安装 mkcert 后重跑本脚本: brew install mkcert"
fi
echo "  2. 设置 → 已下载描述文件 → 安装"
echo "  3. 设置 → 通用 → 关于本机 → 证书信任设置 → 开启完全信任"
echo ""
echo "Mac 换 WiFi / IP 变了请重跑: ./scripts/setup-lan-https.sh"
