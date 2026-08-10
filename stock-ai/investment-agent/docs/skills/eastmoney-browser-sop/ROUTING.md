# 东财 SOP 路由

仅在用户要求单股或 TopN 的东财深度分析时使用。

1. 先由 `stock-opencli/ROUTING.md` 确认采集入口。
2. 用 `scripts/analysis/eastmoney_sop_extract.py` 获取初步报告。
3. 只有需要完整十一维结论时，读取 `SKILL.md` 的“DeepSeek 深度分析”章节。

普通报价、行情和技术面查询不读完整 SOP，也不加载持仓执行卡。
