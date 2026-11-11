# 自用周易系统 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建成可自用的三钱起卦、典籍取辞、DeepSeek 白话解读与复盘应用。

**Architecture:** Vue 3 与 Element Plus 调用 FastAPI；后端纯函数计算卦象和取辞，MySQL 保存不可变的起卦及选文快照。DeepSeek 只解释已选择的材料，失败后基于同一快照重试。

**Tech Stack:** Vue 3、Element Plus、Vite、Python FastAPI、SQLAlchemy、PyMySQL、httpx、pytest。

## Global Constraints

- 前端 Vue 3、Element Plus；后端 Python FastAPI；复用现有局域网 MySQL 实例，建议业务库名 `zhouyi`。
- 密钥只在后端使用，不进入前端、数据库、文档、日志或 Git。
- 六爻数组统一自下而上，展示与编码转换显式处理方向。
- 四类结果概率为 1/8、3/8、3/8、1/8，不采用四类等概率抽样。
- 三爻变须核对原文的前十、后十主次，不将网络简表直接命名为完整朱子规则。
- 用户可见内容、UI 与汇报禁止 emoji。
- 只修改本项目、其设计和计划及项目注册表；保留工作区内其他已有修改。
- 先完成纯规则和来源核验，后实现 API 和界面；不得将缺少原文的记录伪装为已核验。

---

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `zhouyi/backend/zhouyi/core.py` | 三钱随机、六爻变换和卦序映射 |
| `zhouyi/backend/zhouyi/rules.py` | 取辞规则、主辅读与版本 |
| `zhouyi/data/classics.json` | 64 卦映射及经传原文 |
| `zhouyi/data/classics.json` | 带来源、版本及核验状态的注释 |
| `zhouyi/data/rule-evidence.json` | 原文证据、三爻变图表映射和例证 |
| `zhouyi/scripts/import_classics.py` | 可重复运行的典籍导入与结构检查 |
| `zhouyi/backend/zhouyi/config.py` | 指定现有配置文件、提取 DS 与数据库配置 |
| `zhouyi/backend/zhouyi/models.py` | 问卦、典籍、解读尝试、复盘的 SQLAlchemy 模型 |
| `zhouyi/backend/zhouyi/repository.py` | 幂等起卦、快照及状态持久化 |
| `zhouyi/backend/zhouyi/interpretation.py` | DS 请求、输出结构和引用核验 |
| `zhouyi/backend/zhouyi/api.py` | FastAPI 路由、错误转换及前端静态资源 |
| `zhouyi/frontend/src/api.ts` | 统一请求和 API 类型 |
| `zhouyi/frontend/src/components/Hexagram.vue` | 由下至上数据的卦象展示 |
| `zhouyi/frontend/src/views/{Cast,Reading,History,Classics}.vue` | 四个业务页面 |
| `zhouyi/README.md`、`.env.example`、`scripts/start.sh` | 启动、接入及验证说明 |

## Task 1：可验证的起卦与典籍取辞核心

**Files:** 上表 core、rules、data、import_classics；测试 `zhouyi/backend/tests/test_core.py`、`test_rules.py`、`test_corpus.py`。

**Interfaces:**
- `cast_coins() -> list[list[int]]`：六组 2/3 数值，每组三枚。
- `describe_cast(coins: list[list[int]]) -> dict`：返回 `values`、`moving`（1—6）、`original_bits`、`changed_bits`、`original_id`、`changed_id`；bits 自下而上。
- `select_passages(cast: dict) -> dict`：返回 `version`、`reason`、`primary`、`secondary`；引用定位为 `{hexagram_id, kind, position}`，kind 为 judgment、line、use，非爻辞 position 为 null。
- `load_materials(selection: dict) -> list[dict]`：条目包含 `id, role, book, edition, chapter, text, source_url, checksum, verification`。

- [x] 核对《考变占》正文和图49—52，确认三爻变组合顺序：`123 124 125 126 134 135 136 145 146 156 | 234 235 236 245 246 256 345 346 356 456`。前十主本卦、后十主之卦；乾156变恒、234变益，姤156变大壮、234变观。其余图沿用正文所述图例，不声称逐图人工校完。实现时写入 rule-evidence。
- [ ] 先写独立预期的测试，防止老少爻搞反、上下顺序颠倒和用九用六漏判：

```python
def test_all_old_yang_changes_qian_to_kun():
    result = describe_cast([[3, 3, 3]] * 6)
    assert result['values'] == [9, 9, 9, 9, 9, 9]
    assert result['original_id'] == 1
    assert result['changed_id'] == 2
    assert result['moving'] == [1, 2, 3, 4, 5, 6]

def test_single_bottom_change_selects_original_first_line():
    result = select_passages(describe_cast([[3, 3, 3]] + [[2, 2, 3]] * 5))
    assert result['primary'] == [dict(hexagram_id=1, kind='line', position=1)]

def test_three_coins_preserve_distribution():
    from collections import Counter
    from itertools import product
    assert Counter(map(sum, product((2, 3), repeat=3))) == {6: 1, 7: 3, 8: 3, 9: 1}
```

- [ ] 运行 `cd zhouyi/backend && uv run pytest tests/test_core.py tests/test_rules.py -q`，确认缺少功能导致失败。
- [ ] 实现安全随机及固定卦序映射，使用 `secrets.choice((2, 3))`；按 6↔7、9↔8 的动变语义计算之卦阴阳。写齐 0—6 动爻规则及乾坤全变例外。
- [ ] 导入经传，分开保存注疏；保存获取时间、修订或版本、来源与 SHA-256。检查六十四卦唯一覆盖、384 爻、乾坤二用和上下卦映射；不能仅凭抓取成功标为全文校勘完成。
- [ ] 补齐无变、二变上爻主、四变之卦下静爻主、五变之卦静爻、普通六变及三爻变正反例；穷举 4096 种六爻老少状态检查引用能解析且有且仅有一个主读组。
- [ ] 运行核心与资料测试，通过后单独提交本任务文件，提交信息使用中文。

## Task 2：MySQL 持久化及可恢复 API

**Files:** config、models、repository、api；`zhouyi/backend/pyproject.toml`；测试 `test_records.py`、`test_api.py`、`test_config.py`。

**Interfaces:**
- `create_app(settings=None) -> FastAPI`；数据库引擎由 settings 注入，测试使用独立测试库，生产只接 MySQL。
- `POST /api/readings` 输入 `request_id, question, topic, background, horizon`，返回问卦详情。相同 request_id、相同内容返回原记录，不同内容返回 409。
- `GET /api/readings?offset=0&limit=20` 返回 `{items,total}`；`GET /api/readings/{id}` 返回记录和解读尝试。
- `POST /api/readings/{id}/reflections` 输入 `{text}`，追加复盘。
- `GET /api/topics`、`GET /api/classics`、`GET /api/classics/{hexagram_id}` 提供模板与典籍。

- [ ] 写重复请求、内容冲突及失败保留测试：

```python
def test_repeated_submission_keeps_same_cast(client):
    body = dict(request_id='8fd7e50a-3df0-45dd-8b01-100000000001', question='推进项目应注意什么？')
    first = client.post('/api/readings', json=body)
    second = client.post('/api/readings', json=body)
    assert first.status_code in (200, 201)
    assert first.json()['id'] == second.json()['id']
    assert first.json()['cast'] == second.json()['cast']

def test_changed_body_cannot_reuse_request_id(client):
    body = dict(request_id='8fd7e50a-3df0-45dd-8b01-100000000002', question='推进项目应注意什么？')
    client.post('/api/readings', json=body)
    body['question'] = '合作应注意什么？'
    assert client.post('/api/readings', json=body).status_code == 409
```

- [ ] 运行 `uv run pytest tests/test_records.py tests/test_api.py tests/test_config.py -q` 确认失败。
- [ ] 配置明确优先级：环境变量覆盖项目 `.env`，共享文件只提取 DS 字段与 MYSQL_URL；业务数据库名设为 zhouyi，不误用 stock_data。配置检查只输出字段存在性与脱敏连接信息。
- [ ] 建表：唯一 request_id；记录 question/background/horizon、cast JSON、selection JSON、materials JSON；尝试表保存状态、开始结束时间、模型、提示词版本、输出和脱敏错误；复盘表只追加。
- [ ] 用数据库唯一约束处理并发幂等冲突，事务提交问卦后才开放模型生成；找不到记录返回 404，空白问题或过长字段返回 422，数据库故障返回不含连接串的 503。
- [ ] 运行上述测试，再用实际 MySQL 执行独立库建表、事务回滚和幂等集成验证。接入失败时保留纯核心和 API 测试成果，报告实际阻碍，不假称联调通过。
- [ ] 提交本任务文件。

## Task 3：DeepSeek 有据解读及同卦重试

**Files:** interpretation、api 的解读路由；测试 `test_interpretation.py`、`test_recovery.py`。

**Interfaces:**
- `generate_interpretation(question: dict, materials: list[dict], settings) -> dict`。
- 输出 `{summary, traditional, application, actions, citations}`；每个解释段为 `{text, source_ids}`，citations 为 `{source_id, quote}`，quote 必须存在于来源正文。
- `POST /api/readings/{id}/interpretations` 启动解读，已运行返回同一尝试；`GET /api/readings/{id}` 返回状态。解读请求包含独立幂等标识，成功后显式重试创建新版本。

- [ ] 写输入材料限制、错误引用拒绝和失败不改卦测试：

```python
def test_unknown_reference_is_rejected():
    import pytest
    payload = {'summary': {'text': '解释', 'source_ids': ['invented']}}
    with pytest.raises(ValueError):
        validate_interpretation(payload, [{'id': 'known', 'text': '元亨利贞'}])

def test_failed_interpretation_preserves_cast(client, failing_ds, reading):
    before = client.get(f"/api/readings/{reading['id']}").json()['cast']
    client.post(f"/api/readings/{reading['id']}/interpretations", json={'request_id': 'attempt-1'})
    after = client.get(f"/api/readings/{reading['id']}").json()
    assert after['cast'] == before
    assert after['interpretations'][-1]['status'] == 'failed'
```

- [ ] 运行 `uv run pytest tests/test_interpretation.py tests/test_recovery.py -q` 确认失败。
- [ ] 使用 httpx 超时（连接 10 秒、读取 120 秒），只重试连接错误、408、429、5xx，最多 3 次；401/403 直接失败。禁止把响应原文、密钥或完整请求写入错误提示。DS 模型按现有有效配置读取，缺省值在真实调用前核验。
- [ ] 提示词将用户问题与材料作为数据，明确不能执行其中指令；不得改卦或引用未提供的材料。解析结构并验证引用后才保存成功。
- [ ] 用尝试记录与过期租约处理重复请求、进程中断和重新启动；任何重试均使用已保存的选文快照。
- [ ] 模拟超时、限流、无效 JSON、虚构引用及数据库保存失败，再运行一次非个人问题的真实 DS 联调，记录实际模型和状态，不记录密钥。
- [ ] 提交本任务文件。

## Task 4：完整 Vue 与 Element Plus 使用流程

**Files:** frontend、README、启动脚本、`.gitignore`、`.env.example`；修改 `project-registry/projects.json` 注册 zhouyi。

**Interfaces:** 沿用 Task 2—3 的 API 字段；前端只持有 API 数据与表单状态，不持有 DS 或 MySQL 凭据。

- [ ] 写前端行为测试：模板填入后仍可编辑；双击只提交一次；刷新结果页读取原记录；失败重试沿用阅读 ID；卦象顶部显示第六爻。
- [ ] 运行 `cd zhouyi/frontend && npm test -- --run` 确认失败。
- [ ] 使用 Element Plus 中文 locale 建立四页导航。起卦页表单主题可选，背景与时段可选，确认完整问题后提交。请求开始锁定按钮；结果 ID 在响应后写入路由。
- [ ] 结果页用 CSS 绘制阴阳爻，显示本卦/之卦和动爻，自动轮询运行中的解释；错误状态可重试，成功版本可回看，出处折叠展示。文本使用 Vue 插值，不直接插入模型 HTML。
- [ ] 历史页分页及追加复盘，典籍页按卦检索并标明未覆盖注疏。布局在 375px 和 1280px 下保持表单和六爻完整可见。
- [ ] 运行前端行为测试与 `npm run build`；后端托管构建资源，使用显式可配置端口且默认绑定 127.0.0.1。
- [ ] 注册项目入口、启动方式和验证命令；运行后端全部测试与实际 MySQL/DS 集成验证；通过页面完整操作检查起卦至复盘流程。
- [ ] 最终规格审查后再做代码质量审查；修复发现的问题并重跑相关验证；提交本任务文件，交付可访问地址和实际验证结果。

## 计划自审

规格覆盖：Task 1 对应起卦、规则、资料与可追溯性；Task 2 对应主题、存储、历史及复盘；Task 3 对应 DS 和失败恢复；Task 4 对应四页与运行交付。API 和输入输出在各任务中明确。配置文件、个人问卦及复盘不得提交。三爻变主次的最终映射必须以 Task 1 的原图核验成果作为实现输入。

## 实际交付记录

四项开发及规格、质量审查已完成；逐条清单保留原计划，最终验证结果以项目 README 和测试输出为准。数据文件合并为 classics.json，恢复测试纳入 records 与 interpretation 测试。补充简体转换展示及输出，底本独立保留。实现文件尚未提交，保留工作区现有其他修改。
