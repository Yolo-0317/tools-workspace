# DeepSeek AI 交易信号使用指南

> **2026-05 更新**：调用已统一到 `scripts/tools/deepseek_client.py`；能力总览见 **[CAPABILITIES.md](CAPABILITIES.md)**。

## 后端切换（DeepSeek API ↔ Cursor auto）

在 `stock-ai/.env` 设置：

```bash
# 默认：DeepSeek API
LLM_BACKEND=deepseek
DEEPSEEK_API_KEY=sk-...

# 改用 Cursor 订阅（与微信桥相同的 agent login）
LLM_BACKEND=cursor
CURSOR_AGENT_MODEL=auto
```

| 入口 | 函数 | deepseek 默认 | cursor |
|------|------|---------------|--------|
| MCP / 持仓 prompt | `call_deepseek_prompt()` | `deepseek-v4-flash` | `auto` |
| 战报 / SOP messages | `call_deepseek()` | `deepseek-v4-flash` | `auto` |

Cursor 模式：`agent --print --mode ask --trust`，工作区默认 `investment-agent`。无需 `DEEPSEEK_API_KEY`，但单次较慢、不宜高并发 SOP。

## API 封装与模型（LLM_BACKEND=deepseek 时）

| 入口 | 函数 | 默认模型 | 环境变量 |
|------|------|----------|----------|
| MCP / 持仓 prompt | `call_deepseek_prompt()` | `deepseek-v4-flash` | `DEEPSEEK_MCP_MODEL` |
| 战报 / SOP messages | `call_deepseek()` | `deepseek-v4-flash` | `DEEPSEEK_MODEL` |

MCP 内 `_call_deepseek_api()` 已委托至 `call_deepseek_prompt()`。  
个股分析会自动注入决策上下文（`decision_context.py` + 持仓执行卡 + `trading-strategies.md`）。

DeepSeek 环境变量：`DEEPSEEK_API_KEY`（deepseek 模式必需）、`DEEPSEEK_MAX_TOKENS`、`DEEPSEEK_RETRIES` 等。

---

## 功能概述

`deepseek_trade_signal()` 是一个基于 DeepSeek AI 的交易信号分析工具，它：

- 📊 **综合分析**：结合历史日线数据、盘中实时价格、技术指标（MA5/MA20）、量能变化
- 🤖 **AI 决策**：使用 DeepSeek 大模型进行多维度分析，给出买入/卖出/观望信号
- 📝 **详细理由**：提供核心分析理由、止损位、目标位建议
- 🔄 **实时更新**：每分钟更新一次，适合盯盘使用

## 前置条件

### 1. 环境变量配置

```bash
# DeepSeek API 密钥（必需）
export DEEPSEEK_API_KEY="sk-xxxxxxxxxxxxx"

# MySQL 连接串（必需，用于获取历史数据）
export MYSQL_URL="mysql+pymysql://user:pass@localhost:3306/stock_data"
```

### 2. 获取 DeepSeek API Key

1. 访问 [DeepSeek 开放平台](https://platform.deepseek.com/)
2. 注册/登录账号
3. 在"API Keys"页面创建新密钥
4. 复制密钥并设置到环境变量

### 3. 准备历史数据

确保 MySQL 的 `stock_daily` 表已有目标股票/ETF 的历史日线数据（至少 20 条）：

```bash
# 先补齐历史日线
uv run python scripts/sync/sync_tushare_daily_to_mysql.py --mode by_date --days 30
```

## 使用方式

### 方式 1：单次测试（推荐先测试）

运行测试脚本，对比规则策略 vs AI 信号：

```bash
cd tushare-mcp
uv run python tests/manual/test_deepseek_signal.py
```

输出示例：
```
================================================================================
测试 159218 的交易信号
================================================================================

【规则策略 - MA5/MA20】
--------------------------------------------------------------------------------
### 盘中买卖信号报告: 159218
- **盘中日期**: 2025-12-26
- **今开/当前/最高/最低**: 1.568 / 1.625 / 1.637 / 1.555
- **成交量/成交额**: 3100000.0 / 493400000.0
- **涨跌幅(相对昨收)**: 3.64%
- **技术指标(含盘中价)**: MA5=1.5890, MA20=1.5520
- **信号**: 偏买入
- **依据**: 均线多头（MA5 > MA20）；价格在 MA20 之上；盘中强于开盘

【DeepSeek AI 分析】
--------------------------------------------------------------------------------
### DeepSeek AI 交易信号报告: 159218
- **盘中日期**: 2025-12-26
- **今开/当前/最高/最低**: 1.568 / 1.625 / 1.637 / 1.555
- **成交量/成交额**: 3100000.0 / 493400000.0
- **涨跌幅(相对昨收)**: 3.64%
- **技术指标(含盘中价)**: MA5=1.5890, MA20=1.5520

---

- **AI 信号**: 买入
- **核心理由**: 价格突破短期高点且伴随放量；MA5 上穿 MA20 形成金叉；量价配合良好
- **止损位**: 1.540
- **目标位**: 1.680

---

✅ 规则策略与 AI 信号一致！置信度更高
```

### 方式 2：作为 MCP 工具调用（Cursor / Claude Desktop）

在 Claude Desktop 的 MCP 配置中，`deepseek_trade_signal` 会作为工具暴露：

```json
{
  "mcpServers": {
    "tushare-stock": {
      "command": "uv",
      "args": ["run", "tushare_mcp.py"],
      "cwd": "/path/to/tushare-mcp",
      "env": {
        "DEEPSEEK_API_KEY": "sk-xxx",
        "MYSQL_URL": "mysql+pymysql://..."
      }
    }
  }
}
```

然后在 Cursor 对话中：

```
请用 deepseek_trade_signal 分析 600995 的交易信号
```

---

## 盘中做 T（`deepseek_intraday_t_signal`）

专注**日内波段**，与 `deepseek_trade_signal`（趋势 MA5/MA20）互补。

| 对比 | `deepseek_trade_signal` | `deepseek_intraday_t_signal` |
|------|-------------------------|------------------------------|
| 周期 | 数天～数周 | 分钟～小时 |
| 信号 | 买入 / 卖出 / 观望 | 做T买 / 做T卖 / 加减仓 / 不动 |
| 持仓 | 可选 | 建议传 `position_cost`、`position_ratio`（0～1） |

**信号含义**：做T买入（回调支撑低吸）、做T卖出（拉升压力高抛）、加仓、减仓、持仓不动。

**测试**：

```bash
cd stock-ai
uv run python tests/manual/test_t_signal.py
```

**注意**：做 T 仍须遵守持仓执行卡红线（禁追高、禁满仓新开仓等）；MCP 输出已注入决策上下文。

---

## 配置选项

### 温度与模型

- MCP / 持仓类：调用 `call_deepseek_prompt(..., temperature=0.3)`，模型 `deepseek-v4-flash`
- 战报 / SOP 类：调用 `call_deepseek(..., temperature=0.3~0.5)`，模型 `deepseek-v4-flash`

`temperature` 建议 **0.0–0.3** 用于交易信号；0.7+ 不适合决策。

### 提示词与决策上下文

- MCP 内 `_build_deepseek_prompt()` 可扩展技术指标
- 所有 MCP 个股 DeepSeek 分析经 `_maybe_inject_decision_context()` 注入执行卡 + 策略（`SKIP_DECISION_CONTEXT=1` 可跳过）
- 脚本侧：`from scripts.tools.decision_context import inject_decision_context`

## 成本估算

DeepSeek API 定价（参考官网最新）：
- **输入**: ~$0.14 / 1M tokens
- **输出**: ~$0.28 / 1M tokens

单次调用估算：
- 输入: ~1500 tokens（历史 20 天 + 实时数据）
- 输出: ~300 tokens（信号 + 理由）
- 成本: ~$0.0003/次（约 ¥0.002）

每分钟盯 2 个标的（若用 MCP 手动轮询），每天交易时段 4 小时：
- 调用次数: 2 标的 × 60 分钟/小时 × 4 小时 = 480 次/天
- 日成本: ~$0.14（约 ¥1）

**节省成本技巧**：
1. 盘中按需调用 MCP `deepseek_trade_signal`，勿高频轮询
2. 持仓条件监控用 `monitor_holdings_alerts`（规则触发，无 DeepSeek 轮询）
3. 只在关键时段（开盘/收盘前）主动问 MCP

## 注意事项

### 1. 信号不一致时的处理

当规则策略与 AI 信号冲突时：
- ⚠️ **谨慎决策**：两种策略分歧说明市场存在不确定性
- 📊 **参考置信度**：AI 会给出详细理由，结合自己的判断
- 🔍 **查看完整分析**：阅读 AI 的完整输出，了解其推理过程

### 2. API 调用失败处理

脚本已内置异常处理：API 超时/失败不影响规则策略信号；下一轮轮询自动重试。

### 3. 数据延迟

- 东财接口：实时更新（延迟 <1s）
- DeepSeek API：响应时间 1-3s
- 总延迟：约 2-5s（对分钟级盯盘影响可忽略）

### 4. 回测与实盘差异

- AI 输出可能随模型版本、温度参数变化
- 不适合精确回测（使用规则策略做回测基准）
- 建议先用历史数据测试，再上实盘

## 进阶优化

### 1. 添加更多上下文

在 `_build_deepseek_prompt()` 中加入：
- 大盘指数（上证/深证）当日走势
- 行业板块轮动情况
- 近期新闻/政策影响

### 2. 多策略融合

```python
# 同时获取三种信号
rule_signal = intraday_trade_signal(code)  # 规则策略
ai_signal = deepseek_trade_signal(code)    # AI 策略
# ... 可以再加其他策略

# 投票决策
if all([rule=="买入", ai=="买入"]):
    final_signal = "强烈买入"
```

### 3. 日志与统计

记录每次信号到数据库：
- 信号时间、价格、策略类型、置信度
- 后续可做策略评估与优化

## 常见问题

### Q: AI 信号是否比规则策略更准？

A: **不一定**。AI 能综合更多信息，但也可能"想太多"。建议：
- 初期：AI 作为辅助参考，以规则策略为主
- 积累数据后：对比两种策略的实盘表现，调整权重

### Q: 如何避免 AI 输出不稳定？

A: 
1. 降低 `temperature` 到 0.1-0.3
2. 在 prompt 中明确要求"严格按格式输出"
3. 多次调用取平均（成本增加）

### Q: 可以用其他大模型吗？

A: 修改 `scripts/tools/deepseek_client.py` 中的模型与 endpoint，或设置 `DEEPSEEK_MODEL` / `DEEPSEEK_MCP_MODEL` 环境变量（需 API 兼容 OpenAI Chat Completions 格式）。

## 支持

如有问题，请检查：
1. 环境变量是否正确设置
2. MySQL 中是否有历史数据
3. DeepSeek API Key 是否有效
4. 网络是否能访问 DeepSeek API

---

**免责声明**：本工具提供的交易信号仅供参考，不构成投资建议。市场有风险，投资需谨慎。

