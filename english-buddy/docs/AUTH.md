# 登录与家庭账号

English Buddy 是**家庭内网工具**：内置教材**免登录**；**自定义课文**按用户隔离，须登录。

不开放注册。账号由服务端 `.env` 预置，启动时写入 SQLite。

## 行为一览

| 场景 | 是否登录 |
|------|----------|
| 首页选内置课文、开始带读 | 否 |
| 牛津阅读树：未登录 / 非 STT 账号 | 否（**听读**：老师自动念、自动往下；可滑动翻页） |
| 牛津阅读树：`ENGLISH_BUDDY_STT_USERS` 内账号（yueyue / dingdang） | 登录后可选 **跟读**（叮叮 + 麦克风评分）或 **听读**（同左，无需开口） |
| 首页「选课文」里看到自己的自定义课文 | 是 |
| 「自定义课文」页新增 / 预热 / 删除 | 是 |
| WebSocket 带读自定义课文 | 是（Cookie 须有效） |

登录入口：**首页右上角「登录」**，或「自定义课文」页（未登录会先跳登录）。

## 配置账号

在 `english-buddy/.env`：

```env
# 逗号分隔：用户名:密码（改后重启生效，会 upsert 更新密码）
ENGLISH_BUDDY_USERS=dad:你的密码,mom:她的密码,elsa:孩子专用

ENGLISH_BUDDY_REQUIRE_AUTH=1
ENGLISH_BUDDY_SESSION_TTL_HOURS=720
```

可选单独管理员（与 `ENGLISH_BUDDY_USERS` 合并，同名后者覆盖）：

```env
ENGLISH_BUDDY_ADMIN_USER=dad
ENGLISH_BUDDY_ADMIN_PASSWORD=你的密码
```

建议 2～4 个账号（父母各一、孩子专用等）。**勿把真实密码提交 git**。

### 本地 dev vs 公网

| 变量 | 本地 `npm run dev` | 公网 `/english/` |
|------|-------------------|------------------|
| `ENGLISH_BUDDY_COOKIE_PATH` | `/` | `/english/` |
| `frontend/.env` `VITE_BASE_PATH` | `/` | `/english/` |

Cookie 路径必须与前端 `BASE_URL` 一致，否则登录成功但请求不带会话。

```env
# 本地 dev（根目录 .env + frontend/.env 各一份）
ENGLISH_BUDDY_COOKIE_PATH=/
```

公网默认见 `.env.example`（`/english/`）。

### 关闭登录

仅自用、不需要自定义课文隔离时：

```env
ENGLISH_BUDDY_REQUIRE_AUTH=0
```

或未配置 `ENGLISH_BUDDY_USERS` 且 `REQUIRE_AUTH=0` 时，前端不显示登录；自定义课文 API 会拒绝未登录写入。

若 `REQUIRE_AUTH=1` 但 `ENGLISH_BUDDY_USERS` 为空，登录接口返回 503。

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/auth/config` | `{ require_auth: bool }` |
| POST | `/api/auth/login` | body: `{ username, password }`，Set-Cookie `eb_session` |
| POST | `/api/auth/logout` | 清除会话 |
| GET | `/api/auth/whoami` | 当前用户或 `authenticated: false` |

课文列表 `GET /api/lessons?grade=…`：已登录时在同年级内置课文外，**追加**该用户的自定义课文。

## 实现位置

```text
backend/services/auth_settings.py   # 环境变量
backend/services/user_store.py      # 用户表、bootstrap_from_env
backend/services/session_store.py   # eb_sessions
backend/services/auth_deps.py       # require_user / get_optional_user
backend/routers/auth_api.py
frontend/src/auth/session.ts        # apiFetch + credentials
frontend/src/composables/useAuth.ts
```

## 运维

```bash
cd english-buddy
# 改 .env 后
./scripts/restart.sh --build
```

验证：

```bash
curl -s http://127.0.0.1:18787/api/auth/config
curl -s -c /tmp/eb.txt -X POST http://127.0.0.1:18787/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"dad","password":"..."}'
curl -s -b /tmp/eb.txt http://127.0.0.1:18787/api/auth/whoami
```
