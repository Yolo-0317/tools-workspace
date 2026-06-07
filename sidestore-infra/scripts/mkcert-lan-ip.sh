#!/usr/bin/env bash
# 为局域网 IP 生成本地 HTTPS 证书（mkcert），供 Caddy :8443 上 English Buddy 等使用。
# 手机首次需在「证书信任设置」里信任 mkcert 根证书（见脚本末尾说明）。
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LAN_IP="${LAN_IP:-$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)}"
if [[ -z "$LAN_IP" ]]; then
  echo "无法检测局域网 IP，请 export LAN_IP=192.168.x.x 后重试" >&2
  exit 1
fi

if ! command -v mkcert >/dev/null 2>&1; then
  echo "未找到 mkcert，使用 openssl 生成本地自签证书（手机需安装 cert.pem 并信任）…"
  OUT_DIR="$ROOT/certs/lan-ip"
  mkdir -p "$OUT_DIR"
  openssl req -x509 -newkey rsa:2048 \
    -keyout "$OUT_DIR/key.pem" -out "$OUT_DIR/cert.pem" \
    -days 825 -nodes -subj "/CN=${LAN_IP}" \
    -addext "subjectAltName=IP:${LAN_IP},DNS:localhost,IP:127.0.0.1"
  TRUST_FILE="$OUT_DIR/cert.pem"
  TRUST_HINT="安装并信任 ${TRUST_FILE}（描述文件 + 证书信任设置）"
else
  mkcert -install
  OUT_DIR="$ROOT/certs/lan-ip"
  mkdir -p "$OUT_DIR"
  mkcert -cert-file "$OUT_DIR/cert.pem" -key-file "$OUT_DIR/key.pem" \
    "$LAN_IP" localhost 127.0.0.1 ::1
  TRUST_FILE="$(mkcert -CAROOT)/rootCA.pem"
  TRUST_HINT="安装并信任 mkcert 根证书 ${TRUST_FILE}"
fi

CADDYFILE="$ROOT/caddy/Caddyfile"
MARKER="# LAN_IP_HTTPS_SITE"
if grep -q "$MARKER" "$CADDYFILE"; then
  # 更新已有块中的 IP（仅 site 地址行）
  sed -i '' "s|^https://[0-9.]* {$MARKER|https://${LAN_IP} {$MARKER|" "$CADDYFILE"
else
  cat >> "$CADDYFILE" <<EOF

# 局域网 IP 直连 HTTPS（mkcert；$MARKER）
https://${LAN_IP} {$MARKER
	tls /etc/caddy/certs/lan-ip/cert.pem /etc/caddy/certs/lan-ip/key.pem
	encode gzip
	import hub_apps
}
EOF
fi

echo "重启 Caddy…"
docker compose restart caddy

CAROOT="$(mkcert -CAROOT 2>/dev/null || true)"
echo ""
echo "完成。手机带读请用："
echo "  https://${LAN_IP}:8443/english/"
echo ""
echo "iPhone 一次性信任："
echo "  ${TRUST_HINT}"
echo "  设置 → 已下载描述文件 → 安装 → 通用 → 关于本机 → 证书信任设置 → 开启完全信任"
echo ""
EB_ENV="${ROOT}/../english-buddy/.env"
ORIGIN="https://${LAN_IP}:${INTERNAL_HTTPS_PORT:-8443}"
if [[ -f "$EB_ENV" ]]; then
  python3 - "$EB_ENV" "$ORIGIN" <<'PY' || true
import pathlib, sys
path = pathlib.Path(sys.argv[1])
origin = sys.argv[2]
lines = path.read_text(encoding="utf-8").splitlines()
out = []
seen = False
for line in lines:
    if line.startswith("CORS_ORIGINS="):
        seen = True
        parts = [p.strip() for p in line.split("=", 1)[1].split(",") if p.strip()]
        if origin not in parts:
            parts.append(origin)
        out.append("CORS_ORIGINS=" + ",".join(parts))
    else:
        out.append(line)
if not seen:
    out.append("CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173," + origin)
path.write_text("\n".join(out).rstrip() + "\n", encoding="utf-8")
print(f"已写入 english-buddy CORS: {origin}")
PY
  echo "建议: cd ../english-buddy && ./scripts/restart.sh"
else
  echo "若 english-buddy CORS 尚无 ${ORIGIN}，请运行: cd ../english-buddy && ./scripts/setup-lan-https.sh"
fi
