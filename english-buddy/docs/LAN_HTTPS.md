# 内网手机 HTTPS（麦克风）

手机浏览器**只有 HTTPS（或 localhost）才允许麦克风**。内网若用 `http://192.168.x.x:18787` 带读，语音识别/跟读会失败。

## 推荐：mkcert + Caddy :8443

本仓库已通过 **sidestore-infra** 的 Caddy 在 **8443** 提供 HTTPS，证书用 [mkcert](https://github.com/FiloSottile/mkcert) 签发，手机信任一次即可。

### 一键配置

```bash
cd english-buddy
chmod +x scripts/setup-lan-https.sh
./scripts/setup-lan-https.sh
```

脚本会：

1. 检测本机局域网 IP（或 `export LAN_IP=192.168.x.x`）
2. 安装/调用 mkcert，生成 `sidestore-infra/certs/lan-ip/`
3. 在 Caddy 增加 `https://<IP>` 站点块，反代 `127.0.0.1:18787` 的 `/english/`
4. 重启 Caddy 与 English Buddy
5. 在 `english-buddy/.env` 写入 `CORS_ORIGINS` 与 `ENGLISH_BUDDY_COOKIE_SECURE=1`

### 手机访问

```text
https://<你的Mac局域网IP>:8443/english/
```

示例：`https://192.168.1.13:8443/english/`

### iPhone 信任证书（一次性）

**推荐**先装 mkcert（`brew install mkcert`），再重跑 `./scripts/setup-lan-https.sh`：

1. Mac 上 `mkcert -CAROOT` 目录里的 **`rootCA.pem`** 发到手机

若未装 mkcert，脚本会用 openssl 自签，手机须安装 **`sidestore-infra/certs/lan-ip/cert.pem`**。

共通步骤：

2. **设置 → 已下载描述文件** → 安装
3. **设置 → 通用 → 关于本机 → 证书信任设置** → 开启**完全信任**

未做第 3 步时 Safari 会提示证书不受信任，麦克风仍不可用。

### 前提

- English Buddy 已由 launchd 监听 `127.0.0.1:18787`（`./scripts/install-launchd.sh`）
- `sidestore-infra` 的 Docker Caddy 在跑：`cd ../sidestore-infra && docker compose up -d caddy`
- Mac 防火墙允许局域网访问 **8443**

### IP 变更

换网络后 IP 可能变，重跑：

```bash
./scripts/setup-lan-https.sh
```

### 手动分步（与脚本等价）

```bash
cd ../sidestore-infra
./scripts/mkcert-lan-ip.sh
# 在 english-buddy/.env 的 CORS_ORIGINS 加入 https://<IP>:8443
cd ../english-buddy && ./scripts/restart.sh
```

## 为何不用直连 :18787 HTTPS？

后端可挂证书，但手机访问 IP 时仍需受信任证书；统一走 Caddy :8443 与 Home Hub 同端口，配置已成熟。

## 故障排查

| 现象 | 处理 |
|------|------|
| 证书警告 | 手机完成 mkcert 根证书信任（见上） |
| 能开页但不能登录 | 确认 `.env` `CORS_ORIGINS` 含 `https://<IP>:8443`，`ENGLISH_BUDDY_COOKIE_SECURE=1` |
| 麦克风灰色/拒绝 | 地址栏必须是 `https://`，不能是 `http://` |
| WebSocket 失败 | 同上；前端会自动用 `wss://` |
| 404 /english | 确认 launchd 健康：`curl -s http://127.0.0.1:18787/english/api/health` |
