# DeepSeek 成稿后 · 观察者改稿

> **分工**：DeepSeek 负责爆款语气与钩子；**Agent 必做本步**后再 `repush`。
> 角色卡：[account-role-card.md](account-role-card.md)

## 必改两类问题

### 1. 开篇 Discovery 腔（像第一次知道这节目）

| 删/改 | 示例 |
|------|------|
| 昨晚看 / 刚看 / 本来以为 | → `2021年大年初一，央视播了…` |
| 你知道吗 / 你仔细想想 | 删，直接写伏生是谁 |
| 你如果有空去看看 | 删推荐语 |

### 2. 第一人称亲历叙事

DeepSeek 常写「我哭得」「我妈以为」「给我爸发微信」——与本号 **隐形观察者** 冲突。

| 删 | 改用 |
|----|------|
| 我整个人绷不住 | 不少观众愣住 / 倪大红一出场就… |
| 我当时在沙发哭 | 删或改为「场面里」 |
| 我给我爸发微信 | 删，或改为「书房里泛黄旧书」泛指 |
| 标题「我哭得比…」 | 路牌标题，无「我」 |

允许：第三人称、「很多人」「观众」「文献里」；偶尔「普通人」泛指读者。

## Agent 流程

```text
DeepSeek write → scan_deepseek_observer_issues（代码）
  → Agent 全文改观察者口吻（保留 DeepSeek 好用词）
  → 再 scan，0 条 Discovery/第一人称亲历
  → 落 body_cache → repush
```

```bash
cd stock-ai
uv run python -c "
from scripts.tools.wechat_mp_deepseek_polish import scan_deepseek_observer_issues
from scripts.tools.wechat_mp_tv_body_cache import load_tv_body_cache
c = load_tv_body_cache(topic_key='dianji-shangshu')
print(scan_deepseek_observer_issues(c['body_core'], title=c['title']))
"
```

## 代码

`scripts/tools/wechat_mp_deepseek_polish.py`
