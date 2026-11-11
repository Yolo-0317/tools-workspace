# 工作台调用命令

## 环境与路径

- Python：`/Users/huan.yu/dev/tools-workspace/stock-ai/.venv/bin/python`（已有 pandas、requests）。
- 六技能目录：`/Users/huan.yu/.codex/skills/<技能名>`，调用前先读其 SKILL.md。
- 新接口使用 `MX_APIKEY`，通过 `~/.zshenv` 加载私有 `~/.config/miaoxiang/env.zsh`；非 zsh 环境应显式加载该受信任配置或以安全环境映射传入。不要打印密钥。
- 不再用旧 EM_API_KEY / dotenv 命令包装新技能；旧凭据不删除，也不作为鉴权失败的自动回退。
- 输出使用绝对路径 `stock-ai/output/eastmoney/workbench/<上海日期>/<唯一任务目录>`，不要使用上游 `/root/.openclaw/...` 默认路径。

## 六技能入口

下表脚本路径相对各自技能目录。使用参数数组或可靠引号传参。

| 技能 | 脚本 | 参数 |
|---|---|---|
| mx-data | mx_data.py | `'东方财富最新价' /绝对路径/输出目录` |
| mx-search | mx_search.py | `'东方财富最近七天公告与监管风险' /绝对路径/输出目录` |
| mx-xuangu | mx_xuangu.py | `--query '指定日期沪深A股收盘3至200元、成交额至少500万元、涨幅至少3%' --output-dir /绝对路径/输出目录` |
| mx-zixuan | mx_zixuan.py | `query --output-dir /绝对路径/输出目录` |
| mx-moni | SKILL.md 的原生接口 | 根据明确意图选择持仓/资金/委托只读端点，使用已配置密钥；按下述限制执行 |
| mx-poster | mx_poster.py | 先阅读对应子命令；只读 `list --output-dir /绝对路径/输出目录`；发布/互动另需明确请求 |

mx-moni 原脚本在导入时创建硬编码 `/root` 目录，且自然语言分发含交易和发帖动作。本机优先按其 SKILL.md 选择确定的原生接口，用 Python requests 传认证头、30秒超时并保存响应到上述目录；不直接执行含糊的自然语言交易入口，不从报错中推断未成交，不重试不确定的写操作。模拟数据必须标注“模拟”。

mx-zixuan 优先核对原始 JSON `data.allResults.result` 的 columns/dataList/totalRecordCount；日期化指标按 columns.key 读取，不能依赖上游展示器的固定换手率字段。仅预览10行不等于只有10只。

## V3与日线

按 [唯一来源规则](skill-only-data.md)通过 mx-data 获取日线。Tushare适配器退出当前工作流。冻结计算器只保留历史算法与离线测试用途；新mx-data输入适配尚未完成，禁止改写source标签绕过校验。
外部查询前按 [调用预算](call-efficiency.md) 复用结果、记录台账。检查接口业务码、实体、日期和完整性，不能只看退出码。

## 短线补充

龙虎榜读取使用 [短线覆盖说明](short-term-diagnosis.md) 中的 scripts/billboard_input.py；禁止按席位中文名去重。板块筛选必须核对 totalCondition，字段展示要求不能无意变成过滤条件。
