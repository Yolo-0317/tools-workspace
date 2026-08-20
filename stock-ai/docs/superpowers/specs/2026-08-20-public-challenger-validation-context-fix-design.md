# 公开短线挑战者验证上下文修复设计

## 目标

修复公开短线挑战者在 `research` 阶段错误标记为 `TEST`、以及缺少 V3 对照时使用不完整日期并伪造自然日历的问题，使独立门槛始终按真实、完整的阶段交易日历计算。

## 根因

`compare_with_v3()` 同时负责执行轨独立指标和 V3 配对结论，但当前自行从 `v3_days` 或挑战者信号推导日历，并把阶段固定写成 `TEST`。当 `research` 不提供 V3 时，执行轨只有少量有信号日期，函数会把这些日期替换为 63 个连续自然日，导致滚动正收益窗口与真实 126 日验证日历不一致。

V3 缺失本身不是本轮故障。原设计只允许同一冻结测试段的合法 V3 产物参与最终配对；当前挑战者尚未通过验证，不得拼接其他区间或提前读取测试结果。

## 接口设计

为 `compare_with_v3()` 增加两个必填参数：

- `trading_dates: Sequence[date]`：调用方提供当前阶段完整交易日历；
- `segment: str`：仅接受 `VALIDATION` 或 `TEST`。

函数不再从信号日期或 V3 日期推导评估日历，也不再生成合成自然日历。`evaluate_execution_segment()` 直接使用显式参数。

调用约定：

- `build_public_challenger_research()` 传 `split.validation` 与 `VALIDATION`；
- `build_public_challenger_test()` 传 `split.test` 与 `TEST`；
- 当提供 `v3_days` 时，其日期序列必须与 `trading_dates` 完全一致，否则失败关闭；
- 当未提供 `v3_days` 时，独立指标仍按完整阶段日历计算，配对结论保持 `INCONCLUSIVE / V3_COMPARABLE_MISSING`。

## 测试设计

先增加失败测试，再修改实现：

1. 研究构建结果的 `validation_assessment.execution_metrics.segment` 必须为 `VALIDATION`；
2. 研究 assessment 的正收益窗口比例必须与执行轨 `track_metrics` 使用相同 126 日历后的结果一致；
3. 无 V3 时也必须使用调用方显式日历，不得生成合成自然日；
4. 测试构建结果仍标记为 `TEST`；
5. V3 日期与显式阶段日历不一致时失败关闭；
6. 现有 `CHALLENGER_WINS / COMPLEMENTARY / V3_RETAINS / INCONCLUSIVE` 判断保持不变。

## 安全边界

- 不改变信号、成交、成本、容量、门槛或策略参数；
- 不读取或运行一次性测试段；
- 不执行 `freeze` 或 `test`；
- 不生成或拼接 V3 可比产物；
- 不修改现有真实研究产物；修复验证后只允许重新运行 `research` 生成新身份产物；
- 不写持仓、订单、个人决策记忆或凭据。

## 验收

- 相关验证与运行时单元测试全部通过；
- 原公开挑战者测试集合通过；
- 真实 `research` 新产物显示 `segment=VALIDATION`，且 assessment 与执行轨的阶段指标口径一致；
- 新产物仍为 `test_outcomes_read=false`、`trade_permission=NO-TRADE`；
- 不运行 `freeze` 或一次性 `test`。
