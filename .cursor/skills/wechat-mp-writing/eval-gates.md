# 推稿质量门禁（eval-gates）

## 先按稿件来源分流

`wechat_mp_eval --kind hotspot` 以及下文的 75 分、AI 味 20 分规则用于**自动构建的稿件**。它的正文评分仍包含分块标题等自动长稿信号，不能拿来判定用户主动热点稿是否可推。

用户主动热点稿先人工检查一条主线是否贯穿全文，再用下面的只读入口预检机器能够检查的原创字数、来源域、公开文案、结构弱信号与公开合规：

```bash
cd stock-ai
.venv/bin/python -m scripts.tools.wechat_mp_eval --user-hotspot-article output/hotspot_codex.json
```

预检输出“通过”只表示这些可机器检查的项目通过，**仍须人工审稿**：逐项回源核事实，确认标题承诺与核心判断一致，并逐段检查是否增加事实、解释、必要边界或判断。主线散乱、读者问题没有得到回应、同义内容反复出现时，即使预检通过也退回重写，不使用通用分数或“AI 味 0”宣称可推。人工审稿通过后，仍按用户主动稿流程办理图片、交付记录和草稿暂存；本命令不写入公众号。

## 自动门禁（`wechat_mp_push_quality_gate`）

**触发**：`wechat_mp_draft_batch --batch evening` 在合规审计之后、upsert 之前。

**通过条件（全部满足）**：

| 项 | 默认门槛 | 来源 |
|----|----------|------|
| 合规 | 0 条失败 | `wechat_mp_eval` → `check_public_compliance` |
| 总分 | ≥ 75 / 100 | 标题 20 + 开篇 15 + 正文 25 + 去AI 30 + 结尾 10 |
| AI 味 | ≤ 20 / 100 | 机械连接词、禁词、程度词、对称句、emoji 等 |

**verdict 对照**（`wechat_mp_eval` 终端文案）：

- `可进草稿箱` — 自动门禁应通过
- `建议改稿后再推` — 总分 60–74 或 AI 味偏高
- `不合规（须先修）` — 必须先改合规
- `建议重写` — 总分 < 60

## traffic 清单（软门槛）

`--traffic` / 门禁内嵌 traffic：**自动项失败默认不阻断**（`WECHAT_MP_QUALITY_TRAFFIC_BLOCK=0`）。

优先改的自动项（evening 三篇）：

| kind | 高频红灯 |
|------|----------|
| **news** | `title_search_seo`（前 15 字含 A股/快讯/热股名）、`opening_hook` |
| **dragons** | `title_search_seo`（龙头/情绪）、`engagement_hook` |
| **hotspot** | `title_sousou_complete`、`title_opening_aligned`、`hotspot_single_theme`、`hotspot_no_selection_leak`、`reader_no_data_gap_meta` |
| **sector**（手动） | `title_search_seo`（行业/A股）、`opening_conclusion` |

**搜一搜内容规则**已写入 `wechat_mp_sousou_eval.py`：标题路牌完整、开篇同题、hotspot 单主题四段、禁编审话术——`evaluate_article` 在 **标题 / 正文** 维度自动加减分；traffic 清单同步 4 项自动检查。

手动项（`manual: true`）不纳入 exit code，但 Agent 改稿时应核对。

**引流 / 完读手动项**（见 [traffic-copy-craft.md](traffic-copy-craft.md) §九）：开篇尽早落地、论证持续有信息增量、存在值得转述的事实或判断、正文收束与稿末关注句不重复。用户主动热点不按固定字数或钩子数量评分；事实与适用范围先于语言评分。

**读者嘴替人工项**：写明本稿替哪类读者说话、他看到已核事实后最想问什么；检查正文是否较早回应了这句话，批评是否落到可观察的行为或信息落差。事实不充分时保留不确定性，不虚构群体愤怒、采访引语或对方动机；事实充分时不靠反复免责声明撤回判断。此项适用于公众号文章的人工审阅，影视与典籍对应读者的感受和好奇，不强求批评。它不纳入自动 exit code，也不以“我替读者问一句”等固定词句作机器检测。

## 命令速查

```bash
cd stock-ai

# 整批（与 evening 推稿同 env）
uv run python -m scripts.tools.wechat_mp_push_quality_gate --batch evening

# 单 kind
uv run python -m scripts.tools.wechat_mp_push_quality_gate --kinds news sector

# 仅 eval、自定义门槛
uv run python -m scripts.tools.wechat_mp_eval --kind news --traffic --min-score 75 --max-ai-flavor 20

# 只看结构不推微信
uv run python -m scripts.tools.wechat_mp_draft_batch --batch evening --dry-run
```

## 与合规审计的关系

| 层 | 模块 | 时机 |
|----|------|------|
| 推荐安全 | `audit_recommendation_safety` | batch 推稿（`WECHAT_MP_STRICT_COMPLIANCE`） |
| 公开合规 | `check_public_compliance` | eval / 门禁内 |
| 质量分 | `evaluate_article` | eval / 门禁内 |

门禁未过 **不会** 写入草稿箱（strict 模式）；改稿后重跑 `wechat_mp_draft --kind <k>` 或整批 batch。
