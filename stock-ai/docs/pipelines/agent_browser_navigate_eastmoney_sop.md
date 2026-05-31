# Agent 浏览器采集 SOP（东财，多维数据）

本文档用于让 Agent 通过 `browser_navigate`（Cursor 浏览器 MCP）执行同一套流程，采集：

- 基本面
- 资金面
- 北向资金
- 财务面
- 消息面
- 研报面

示例，其他股票仅替换代码和交易所前缀即可复用。

---

## 1. 目标与URL规则

以 `001289`（深市）为例：

- 行情页：`https://quote.eastmoney.com/sz001289.html`

代码映射规则：

- `60*`/`68*` -> `sh` / `SH`
- 其他A股常见代码 -> `sz` / `SZ`

---

## 2. Agent 执行顺序（固定流程）

1. **环境检查与锁定**：调用 `browser_tabs` `action=list` 检查当前标签页。若存在可用标签页，先调用 `browser_lock` 锁定浏览器，防止人工干扰。
2. **页面导航**：调用 `browser_navigate` 打开目标股票行情页（如 `https://quote.eastmoney.com/sh600873.html`）。
3. **智能等待与验证**：**摒弃固定长等待**。采用短轮询策略（如等待 2 秒 -> `browser_snapshot` 检查目标区域 -> 若未加载完毕再等 2 秒），确保 指定的选择器 等动态数据已渲染（不再是 `-` 占位符）。
4. **精准数据采集**：调用 `browser_snapshot` 并传入 `selector`（如 `.brief_info_c` 或 `.sider_quote_price2`）精准提取所需 DOM 结构，避免获取全页冗余数据。
5. **解锁与清理**：采集完成后，调用 `browser_unlock` 解除锁定。
6. **关闭标签页**：调用 `browser_tabs` `action=close` 关闭当前临时标签页，保持环境整洁。

---

## 3. 各维度字段“从哪里取”

### 3.1 基本面（行情页）

采集方式：DOM_SELECTOR
页面：<https://quote.eastmoney.com/sh600873.html>
选择器：.brief_info_c
字段映射：
今开 <- label=今开 右侧值
昨收 <- label=昨收 右侧值

基本面可采字段
选择器 .brief_info_c 的div获取：

- 价格类：`最新价`、`涨跌`、`涨跌幅`、`今开`、`昨收`、`最高`、`最低`、`涨停`、`跌停`
- 成交类：`成交量`、`成交额`、`换手率`、`量比`
- 其他基本面：市盈(动) 8.02、总市值 323.3亿、市净 2.01、流通市值 323.3亿

价格类：今开 11.25、最高 11.63、涨停 12.34、昨收 11.22、最低 11.18、跌停 10.10
成交类：换手 1.89%、成交量 53.02万、量比 0.81、成交额 6.082亿
其他基本面：市盈(动) 8.02、总市值 323.3亿、市净 2.01、流通市值 323.3亿

#### 3.1.1 委比/委差、买卖盘具体档位

选择器 .sider_quote_price sider_quote_price2的div获取

- `委比`
- `委差`
- `卖一价`、`卖一量`
- `卖二价`、`卖二量`
- `卖三价`、`卖三量`
- `卖四价`、`卖四量`
- `卖五价`、`卖五量`
- `买一价`、`买一量`
- `买二价`、`买二量`
- `买三价`、`买三量`
- `买四价`、`买四量`
- `买五价`、`买五量`

### 3.2 资金面

直接在行情页获取（无需额外打开页面）：`https://quote.eastmoney.com/sh600873.html`

选择器 `.zjl_charts` 或者直接提取整个页面的文本。

获取：

- 实时成交分布：`超大单(流入/流出)`、`大单(流入/流出)`、`中单(流入/流出)`、`小单(流入/流出)`

### 3.3 财务面

优先页面（F10财务分析）：`https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH600873&color=b#/cwfx`

选择器：由于是 SPA 页面，建议直接提取 `#app` 内部的文本，或者使用更宽泛的 `body`。

`公司核心数据`

- `收益`、`PE(动)`
- `每股净资产`、`市净率`
- `总营收`、`总营收同比`
- `净利润`、`净利润同比`
- `毛利率`、`净利率`
- `ROE`、`负债率`
- `总股本`、`总值`
- `流通股`、`流值`
- `每股未分配利润`

### 3.4 消息面

打开页面 `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH600873&color=b#/zxgg`
选择器：由于是 SPA 页面，建议直接提取 `#app` 内部的文本，或者使用更宽泛的 `body`。
（OpenCLI 在浏览器上下文中等待 `#app` 加载后，用 `eval` 提取 `innerText` 交给大模型分析）。
获取相关资讯、相关公告以及资讯摘要。

### 3.6 研报面

打开页面 `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH600873&color=b#/yjbg`

选择器：由于是 SPA 页面，建议直接提取 `#app` 内部的文本，或者使用更宽泛的 `body`。

获取近期研究报告的标题、摘要、机构评级等信息。

### 3.7 所属板块

打开页面 `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH600873&color=b#/hxtc`

选择器：`#app` （或直接提取页面文本）

获取该股票所属的行业分类（如一级、二级、三级行业）以及所属的概念板块（如红利股、合成生物等）。

### 3.8 盈利预测

打开页面 `https://emweb.securities.eastmoney.com/pc_hsf10/pages/index.html?type=web&code=SH600873&color=b#/ylyc`

选择器：由于是 SPA 页面，建议直接提取 `#app` 内部的文本，或者使用更宽泛的 `body`。

获取评级统计、机构预测、预测统计、预测明细

## 4. 复制到其他股票时只改

1. 代码（6位）

其余采集步骤、字段来源、判定口径保持不变。

---
