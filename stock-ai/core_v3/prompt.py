# config.py
import os

# DeepSeek API 配置
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "your-api-key-here")
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 选股阈值
TECH_SCORE_THRESHOLD = 65  # 技术面最低分

# 九维分析 Prompt 模板
NINE_DIMENSION_PROMPT = """
你是一位专业的A股量化分析师，拥有10年以上投资研究经验。请对以下股票进行九维分析。

## 分析标的
{stock_name}（{stock_code}）

## 基础数据
- 当前价格：{price}元
- 今日涨跌幅：{change}%
- 技术面评分：{tech_score}/100
- 技术面评级：{tech_rating}
- 关键支撑：{support}元
- 关键压力：{resistance}元

## 分析要求
1. 请**开启联网搜索**，获取该股票的最新资金面、基本面、财务面、估值面、消息面、情绪面、宏观面、筹码面数据
2. 按以下九维框架输出分析报告：
   - 技术面、资金面、消息面、基本面、财务面、估值面、情绪面、宏观面、筹码面
3. 每个维度给出：
   - 评分（1-5星）
   - 核心依据（具体数据）
4. 输出综合评级和操作建议（买点、止损、目标、仓位）
5. 最后给出风险提示和一句话总结

## 输出格式要求
请使用 Markdown 格式，包含表格和清晰的层级结构。
"""