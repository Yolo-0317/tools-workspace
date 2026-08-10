# 公司电脑运行公众号写稿

本方案只迁移「牛马也智能」的选题、写稿、质检和草稿箱写入。公司电脑独立运行；不需要连接家里的 MySQL、Docker、微信机器人、东方财富证券或持仓数据。

## 适用范围

| 可直接运行 | 暂不迁移 |
|---|---|
| `hotspot_*` 社会/财经热点草稿 | `top5`、`dragons` 等依赖 MySQL 的财经选股稿 |
| `tv_trial` 影视讨论稿 | 日线同步、选股、持仓监控、微信推送 |
| 草稿质量门禁、人工公众号后台发布 | 自动定时任务与家庭 Mac 的 launchd/Docker |

公司端仍需本机的 Cursor CLI、OpenCLI Chrome 扩展和公众号 API 凭证。公众号 API 只会写草稿；发布继续在 `mp.weixin.qq.com` 人工确认。

## 首次安装

```bash
git clone <你的 tools-workspace 仓库地址>
cd tools-workspace/stock-ai
uv sync --group dev

# 安装 Cursor CLI 后，在公司电脑单独登录
agent login

# 安装 OpenCLI 与 Chrome 扩展；确认扩展已连接
opencli doctor

# 只复制模板，绝不从家里拷贝 .env、token 或 ~/.wechat-acp
cp .env.company-wechat.example .env
```

在公司电脑的微信公众平台开发后台，将该电脑所在网络的**公网出口 IP**加入 IP 白名单，再填写 `.env` 中的 `WECHAT_MP_APPID`、`WECHAT_MP_SECRET`、`WECHAT_MP_WHITELIST_IP`。企业网络常有代理或动态出口；每次换网络后都要重新检查。

```bash
./scripts/verify_company_wechat.sh
```

该命令只检查公网 IP、公众号 API 和必要命令；不会调用 LLM、不会写草稿、不会发微信/飞书通知。

## 日常写稿

```bash
cd tools-workspace/stock-ai

# 指定热点，先干跑
WECHAT_MP_HOTSPOT_TOPIC='你的选题' \
  uv run python -m scripts.tools.wechat_mp_draft_batch \
  --batch hotspot_afternoon --dry-run --no-notify

# 确认后写入公众号草稿箱
WECHAT_MP_HOTSPOT_TOPIC='你的选题' \
  uv run python -m scripts.tools.wechat_mp_draft_batch \
  --batch hotspot_afternoon --no-notify

# 影视讨论稿
uv run python -m scripts.tools.wechat_mp_draft_batch \
  --batch tv_trial --dry-run --no-notify
```

草稿生成成功后，在公众号后台检查封面、原创、分类与话题标签，再人工发表。保持 `WECHAT_MP_AUTO_PUBLISH=0`。

## 凭证与安全边界

- `.env` 仅放在公司电脑并保持 git ignored；不要提交、发微信、放云盘或同步 `~/.wechat-acp/`。
- 不迁移家中 Mac 的 `MYSQL_URL`、`TUSHARE_TOKEN`、`DEEPSEEK_API_KEY`、券商/JYWG 登录态和微信机器人 token。
- 若公司网络不能将固定出口 IP 加入公众平台白名单，只能干跑写作；草稿写入需回到已白名单网络。
- 不安装 launchd 或 Docker scheduler，避免公司电脑在后台自动写稿或发通知。

## 故障速查

| 现象 | 处理 |
|---|---|
| `40164` / IP 白名单错误 | 执行 `./scripts/verify_company_wechat.sh`，将显示的公网 IP 加入公众平台白名单后重试。 |
| `agent` 不存在或未登录 | 安装 Cursor CLI，并执行 `agent login`。 |
| OpenCLI 无法连接 | 在公司 Chrome 安装/启用扩展，运行 `opencli doctor`。 |
| 缺少 MySQL | 改用 `hotspot_*` 或 `tv_trial`；不要在公司端运行 `evening`、`top5`、`dragons`。 |
