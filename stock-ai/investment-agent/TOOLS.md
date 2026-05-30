# TOOLS.md - Local Notes

Skills define _how_ tools work. This file is for _your_ specifics — the stuff that's unique to your setup.

## What Goes Here

Things like:

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## 项目路径（investment-agent）

**本目录**：`/Users/yolo/dev/yolo/tools-workspace/stock-ai/investment-agent`
**stock-ai 根目录**：`/Users/yolo/dev/yolo/tools-workspace/stock-ai`（行情脚本、MySQL、选股输出）
**持仓 CSV**：`holdings.csv` → `../holdings/current.csv`
**QClaw 原工作区**：`~/.qclaw/workspace`（可用 `scripts/sync-from-qclaw.sh` 同步）

## OpenCLI Browser（浏览器自动化）

**路径**：`/Users/yolo/.nvm/versions/node/v24.14.1/bin/opencli`
**版本**：1.7.3
**注意**：需先 `source ~/.zshrc` 加载 NVM 环境，或在命令前加 PATH 导出

### 快速调用（推荐写进脚本）
```bash
export PATH="$HOME/.nvm/versions/node/v24.14.1/bin:$PATH"
opencli --version    # 验证连通性
opencli browser state  # 查看当前页面
```

### 常用命令
| 命令 | 作用 |
|------|------|
| `opencli browser open <url>` | 打开URL |
| `opencli browser state` | 当前页面状态+可交互元素 |
| `opencli browser screenshot [path]` | 截图 |
| `opencli browser click <index>` | 点击元素（按state输出的索引） |
| `opencli browser type <index> <text>` | 点击后输入文本 |
| `opencli browser select <index> <option>` | 下拉选择 |
| `opencli browser keys <key>` | 按键盘键 |
| `opencli browser wait selector <sel> [time]` | 等元素出现 |
| `opencli browser wait text <text> [time]` | 等文本出现 |
| `opencli browser wait time <seconds>` | 等N秒 |
| `opencli browser eval <js>` | 在页面内执行JS |
| `opencli browser network` | 查看捕获的网络请求 |
| `opencli browser close` | 关闭浏览器窗口 |

### 工作流（东方财富数据采集标准流程）
1. `opencli browser open "https://quote.eastmoney.com/sh600995.html"`
2. `opencli browser wait time 3`（等JS渲染）
3. `opencli browser state`（查看页面元素）
4. `opencli browser screenshot`（截图确认）
5. 按需 click / type / eval 获取数据

### 调用失败复盘检查项
- ❌ `command not found`：新终端窗口未 source ~/.zshrc → 先 `source ~/.zshrc`
- ❌ `unknown command`：opencli 版本不对 → 检查 PATH 是否指向正确版本
- ❌ 页面空白/超时：东方财富JS渲染慢 → 页面 render 慢，多等几秒
- ❌ Chrome 未检测到：浏览器已关闭 → 重开Chrome或用 `opencli browser open` 触发

### 东财SOP脚本（自动处理NVM）
```bash
~/.qclaw/workspace/skills/eastmoney-browser-sop/scripts/extract_stock_data_opencli.py
# 脚本内已内嵌 NVM 环境加载，直接 python3 调用即可
```

---

## OpenClaw 服务管理

**CLI 路径**：`/Users/yolo/Library/Application Support/QClaw/openclaw/config/bin/openclaw`
（OpenClaw 主程序，非 opencli）

- `openclaw gateway status` — 查看 Gateway 状态
- `openclaw agent --local -m "消息"` — 本地单次 agent 调用

---

## EasyOCR（截图文字识别）

**用途**：识别股票APP截图中的持仓数据
**环境**：Python3 + torch 2.8.0 + opencv-python-headless + easyocr

```python
import easyocr
reader = easyocr.Reader(['ch_sim', 'en'], gpu=False)
result = reader.readtext('/path/to/image.png')
```

---

## Tushare（股票数据API）

**Token**：`c939432a7e051c71fdfabe24d917ef308116e78c4c559132d0bef75f`
**已配置环境变量**：`TUSHARE_TOKEN`

```python
import tushare as ts
pro = ts.pro_api('c939432a7e051c71fdfabe24d917ef308116e78c4c559132d0bef75f')
df = pro.daily(start_date='20260424', end_date='20260425')
```

**查询脚本**：`/tmp/get_holdings.py`（快速查持仓行情）

---

## MySQL（本地行情数据库）

**Docker容器**：运行中
**表名**：`stock_data.stock_daily`（注意不是 `daily`）
**关键字段**：`ts_code`（不带交易所后缀）、`pct_chg`（不是 `pct_change`）
**连接URL**：已配置环境变量 `MYSQL_URL`

---

## DeepSeek API

**环境变量**：`DEEPSEEK_API_KEY`
**用途**：股票深度分析（11维度框架）
**注意**：响应长度限制 tok=12000，分两轮调用防截断

---

## 浏览器MCP（命名空间注意）

**问题**：工具注册在 `mcp__browser` 但 gateway 调用 `browser` 端点，命名空间不匹配
**状态**：暂未修复，opencli browser 作为主要替代

---

## Homebrew

**注意**：自动更新延迟较长（~2min），安装 CLI 时注意
**环境变量**：`HOMEBREW_NO_AUTO_UPDATE=1` 可禁止自动更新

---

## 工具选用决策框架（2026-05-14更新）

### 三类工具适用场景

| 工具 | 用途 | 适用场景 | 不适用场景 |
|------|------|---------|-----------|
| **东财宏观快讯**（`fetch_eastmoney_macro_news.py`） | Playwright 抓取 7×24 财经快讯 | 每日宏观早报、定时推送 | 个股财务/筹码数据 |
| **ProSearch**（online-search skill） | 关键词搜索新闻/事件/实时信息 | 查"为什么涨/跌"、事件原因补充 | 查个股财务/筹码数据 |
| **opencli browser**（浏览器自动化） | JS渲染页面数据抓取 | 个股行情、财务数据、筹码分布、机构持仓 | 批量宏观快讯（用脚本） |
| **东财API**（curl） | 轻量级实时行情 | 指数/个股实时价格、每日战报 | 需要财务/基本面数据 |

### 东财宏观财经快讯 / 每日战报（Playwright）

```bash
cd ../  # stock-ai 根目录

# 完整战报（与 QClaw daily_briefing 定时任务一致，含 DeepSeek 解读）
FETCH_ONLY=1 ./push_daily_briefing_wechat.sh 09:00
./push_daily_briefing_wechat.sh 15:00

# 首次/重装后：把 QClaw 4 个 daily_briefing 任务切到新脚本
./scripts/install-daily-briefing-cron.sh

# 仅东财快讯
uv run python -m scripts.tools.fetch_eastmoney_macro_news --limit 15
```

数据源：`https://kuaixun.eastmoney.com/`（主）+ 腾讯行情（大盘/国际/持仓）

### ProSearch（在线搜索）

**脚本路径**：`/Users/yolo/Library/Application Support/QClaw/openclaw/config/skills/online-search/scripts/prosearch.cjs`

```bash
# 基础搜索（中文关键词）
node '<SCRIPT_PATH>/scripts/prosearch.cjs' --keyword="A股 5月14日 下跌原因"

# 24小时时效性搜索
node '<SCRIPT_PATH>/scripts/prosearch.cjs' --keyword="特朗普 访华 A股" --freshness=24h

# 新闻类搜索
node '<SCRIPT_PATH>/scripts/prosearch.cjs' --keyword="最新市场分析" --industry=news
```

### 东财实时行情API（curl）

```bash
# 三大指数实时行情
curl -s "https://push2.eastmoney.com/api/qt/list.np/get?fltt=2&secids=1.000001,0.399001,0.399006&fields=f2,f3,f4,f12,f14"

# 个股实时行情（secids格式：1=沪市，0=深市）
curl -s "https://push2.eastmoney.com/api/qt/list.np/get?fltt=2&secids=1.600995,0.003816,1.601985&fields=f2,f3,f4,f12,f14"
```

### 工具选用原则
- **宏观财经早报** → `fetch_eastmoney_macro_news.py`（东财 Playwright）
- **事件/原因类问题**（为什么涨/跌？）→ ProSearch 搜索（补充）
- **个股基本面数据**（财务/筹码/机构）→ opencli 浏览器
- **快速价格查询**（每日战报）→ 东财 API curl

### ⚠️ 教训（2026-05-14）
- ❌ 不要说"AI没有实时行情数据，建议用户自行查看"
- ✅ 直接用ProSearch搜索 或 curl东财API获取实时数据
- ❌ 不要混淆opencli和ProSearch，明确区分用途

---

Add whatever helps you do your job. This is your cheat sheet.
