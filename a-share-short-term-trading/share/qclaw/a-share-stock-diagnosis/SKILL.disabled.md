---
name: a-share-stock-diagnosis
description: >-
  无 MySQL 的 A 股个股诊断与手工持仓指导。当用户要求个股诊断、股票分析、
  持仓建议、减仓、止损、支撑位、压力位，或提供股票代码/名称询问交易指导时使用。
metadata:
  openclaw:
    version: "1.0.0"
---

# A 股个股诊断共享版

本 Skill 通过附带的确定性 Python 脚本获取公开行情并计算结论。不得由模型自行计算或改写脚本给出的价格、方向、时段和数量。

## 输入收集

普通个股诊断只需要六位股票代码或股票名称。

持仓诊断至少需要：

- 当前持仓股数 `shares`
- 成本价 `cost_price`

当前可卖股数 `available_shares` 可以未知。缺少 `shares` 或 `cost_price` 时，每次只询问一个缺失值。用户未提供可卖股数时，不得擅自按持仓股数代替。

## 执行

将本文件所在目录记为 `<skill_dir>`，执行：

```bash
python3 "<skill_dir>/scripts/diagnose.py" --symbol "<股票代码或名称>" --output json
```

持仓诊断执行：

```bash
python3 "<skill_dir>/scripts/diagnose.py" --symbol "<股票代码或名称>" \
  --shares <持仓股数> --cost-price <成本价> \
  --available-shares <当前可卖股数> --output json
```

可卖股数未知时省略 `--available-shares`。不要把用户输入写入文件、配置、记忆或日志。

`--at` 仅用于带时区的历史复现测试，不允许用它让用户手工指定交易时段。

## 输出规则

解析脚本输出的单个 JSON 对象，然后用中文给出：

1. 当前交易时段、数据时间和数据新鲜度；
2. `decision`、`reason` 和 `next_action`；
3. 支撑、压力、触发、失效和第一减仓价；
4. 有持仓时展示盈亏、建议数量和 T+1 可卖限制；
5. 原样保留 `warnings` 和安全降级原因。

任何结果都必须说明 `actionable=false`，不得说成已获交易许可。筹码只能称为 CYQ 估算，不得称为交易所披露的真实持仓成本。

脚本失败、数据缺失、交易日历未知或 `errors` 非空时，不得切换为无证据的自由分析，也不得补造行情、日期、价位或数量。

## 安全边界

- 不访问券商、浏览器 Cookie、账户文件或 QClaw 用户记忆。
- 不连接数据库，不读取 `.env`，不要求 API Key。
- 不自动下单，不发送消息，不创建定时任务。
- 不承诺收益；输出仅用于辅助用户自行判断风险。

