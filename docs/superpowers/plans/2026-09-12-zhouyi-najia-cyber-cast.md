# 观易六爻纳甲与赛博起卦 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有观易应用中加入可选六爻纳甲排盘、可追溯的北京时间信息，以及无铜钱的赛博逐爻起卦动画。

**Architecture:** 后端继续先生成并保存不可变的三钱随机结果；经典模式沿用原流程，纳甲模式调用独立历法和排盘纯函数生成版本化快照。前端在收到已保存记录后播放 Canvas 2D 粒子汇聚和 CSS 逐爻扫描，再进入同一结果页；测试注入假解释器，禁止真实 DeepSeek。

**Tech Stack:** Python 3.11、FastAPI、SQLAlchemy、lunar_python 1.4.8、pytest、Vue 3、Element Plus、Canvas 2D、Vitest。

## Global Constraints

- 用户可见文字全部使用简体中文，不展示铜钱或古钱币图形。
- 两种模式共享三钱法 1:3:3:1 概率，但经典规则和纳甲规则分别显示。
- 纳甲默认北京时间，允许修改日期、时间和所在地；第一版采用北京时间零点换日，不计算真太阳时。
- 不收集姓名、性别和生辰八字。
- 测试不读取 DeepSeek 密钥、不访问 DeepSeek 网络；真实模型联调不属于本计划。
- 旧记录按经典模式读取，不重算旧卦；相同 request_id 永远返回同一记录。
- 动画约 5—7 秒、可跳过，支持减少动态效果和低性能降级。

---

## 文件职责

| 文件 | 职责 |
| --- | --- |
| `zhouyi/backend/zhouyi/calendar.py` | 输入时间标准化、北京时间干支、旬空和历法版本 |
| `zhouyi/backend/zhouyi/najia.py` | 八宫、纳支五行、世应、六亲、六神及基础月日关系纯函数 |
| `zhouyi/backend/zhouyi/api.py` | 模式与时间字段校验、创建经典或纳甲快照、解释器依赖注入 |
| `zhouyi/backend/zhouyi/repository.py` | 旧记录兼容和重复请求内容一致性 |
| `zhouyi/backend/tests/test_calendar.py` | 时区、干支、旬空和边界日期 |
| `zhouyi/backend/tests/test_najia.py` | 已知装卦、八宫、世应、六亲和六神 |
| `zhouyi/backend/tests/test_api.py` | 新旧请求、幂等、无真实模型测试门禁 |
| `zhouyi/frontend/src/components/CyberCast.vue` | Canvas 粒子、逐爻扫描、跳过及减少动态 |
| `zhouyi/frontend/src/cast-animation.ts` | 六阶段动画状态机和性能降级纯逻辑 |
| `zhouyi/frontend/src/views/CastView.vue` | 模式、北京时间、所在地、重复起卦提醒和动画承载 |
| `zhouyi/frontend/src/views/ReadingView.vue` | 经典与纳甲结果分区展示 |
| `zhouyi/frontend/src/types.ts` | 新请求、历法和纳甲快照类型 |

### Task 1: 历法输入和北京时间干支

**Interfaces:**
- Produces: `normalize_cast_time(value: str | None) -> CalendarSnapshot`
- `CalendarSnapshot` 包含 `input_time`、`beijing_time`、`timezone`、`year_ganzhi`、`month_ganzhi`、`day_ganzhi`、`hour_ganzhi`、`day_stem`、`day_branch`、`month_branch`、`xunkong`、`version`。

- [ ] 在 `test_calendar.py` 写默认北京时间、显式时区转换、无效时间和已知干支/旬空用例，并用 monkeypatch 固定当前时间。
- [ ] 运行 `../.venv/bin/python -m pytest tests/test_calendar.py -q`，确认模块缺失而失败。
- [ ] 在 `pyproject.toml` 固定 `lunar_python==1.4.8`，实现 `calendar.py`；明确输入必须含时区，输出统一为 `Asia/Shanghai`，使用 `Solar.fromYmdHms(...).getLunar().getEightChar()`。
- [ ] 运行历法测试并更新 `requirements.lock.txt`。

### Task 2: 京房八宫纳甲排盘

**Interfaces:**
- Consumes: `describe_cast()` 输出与 `CalendarSnapshot`。
- Produces: `build_najia(cast: dict, calendar: dict, topic: str) -> dict`，包含规则版本、宫、宫五行、世应、用神候选、本卦六爻、变卦六爻和结构化观察。

- [ ] 在 `test_najia.py` 写乾、坤、八纯卦、游魂归魂、世应位置、八卦内外纳支、日干六神、六亲及旬空标记用例。
- [ ] 运行测试，确认 `zhouyi.najia` 缺失而失败。
- [ ] 在 `najia.py` 定义不可变的八宫序列表、世爻表、八卦纳支表、五行映射、六亲关系和六神起始表；按自下而上六爻顺序输出。
- [ ] 为月建、日辰的值、冲、合、月破、旬空生成确定性标签；无法从固定规则推出时返回空标签，不生成预测句。
- [ ] 运行 `test_najia.py` 及全部核心规则测试。

### Task 3: 保存模式与纳甲快照

**Interfaces:**
- `POST /api/readings` 新增 `mode: "classic" | "najia"`、`cast_time: ISO-8601 | null`、`location: str`。
- 阅读记录新增顶层 `mode`、`calendar` 和 `najia`；旧记录序列化时补 `mode=classic`、`calendar=null`、`najia=null`。

- [ ] 扩展 `test_records.py` 和 `test_api.py`：经典默认、纳甲创建、无时区拒绝、相同 request_id 内容冲突、旧记录兼容。
- [ ] 增加“测试解释器”用例：构造应用时注入生成函数；测试环境若没有注入则禁止启动任何真实 HTTP 模型请求。
- [ ] 先运行新增用例确认失败，再修改 `models.py`、`repository.py`、`manage.py` 和 `api.py`；以可重复迁移增加 JSON 字段或将新快照存入现有记录的版本化 JSON，选择对旧数据改动最小的方案。
- [ ] 运行后端全部测试；用实际 MySQL 只执行建表升级、创建纳甲记录、读取和幂等检查，不创建解释尝试。

### Task 4: 赛博起卦动画

**Interfaces:**
- `makeCastTimeline(values: number[]) -> CastFrame[]` 返回六个自下而上阶段。
- `CyberCast` 接收 `cast`、`durationMs=6000`，发出 `complete` 和 `skip`。

- [ ] 在 `cast-animation.test.ts` 写六阶段顺序、6/9 动爻标记、减少动态立即完成和降级粒子数量用例；在 `flows.test.ts` 写提交成功后先出现动画、跳过后进入结果、重复请求不重新起卦。
- [ ] 运行 Vitest 确认组件和状态机缺失而失败。
- [ ] 实现 `cast-animation.ts` 和 `CyberCast.vue`：Canvas 中复用 150—250 个粒子，`requestAnimationFrame` 绘制三束信号，CSS 显示爻线和朱红动爻脉冲；页面隐藏时暂停，帧率持续偏低时减半粒子。
- [ ] 在 `CastView.vue` 中收到后端记录后保存记录 ID并播放动画，结束或跳过才跳转；`prefers-reduced-motion` 时使用短淡入。
- [ ] 运行前端测试与构建，并在 375px、1280px 检查无横向溢出。

### Task 5: 纳甲表单与结果页

**Interfaces:**
- 起卦模式写入请求；纳甲模式显示时间和所在地输入。
- 结果页只在 `mode=najia` 时显示排盘表和“当前按北京时间、零点换日、不使用真太阳时”。

- [ ] 扩展 `flows.test.ts`：模式切换、默认当前时间、编辑时间地点、纳甲字段显示、旧记录经典显示。
- [ ] 修改 `types.ts`、`CastView.vue` 和 `ReadingView.vue`，添加模式说明、排盘六爻表、世应、六亲、六神、月日标签和用神候选；输出统一称“卦象启示与行动参考”。
- [ ] 增加本地历史匹配：同一规范化问题存在近期记录时显示“先回看原卦”链接，但允许继续。
- [ ] 运行前端测试、类型检查和生产构建。

### Task 6: 文档、全量验证和提交

- [x] 更新 `zhouyi/README.md`、设计实现记录和项目注册信息，写明两种模式、历法口径、资料覆盖、动画降级及测试禁止真实模型。
- [x] 运行 `../.venv/bin/python -m pytest -q`，要求无失败且模型 HTTP 调用计数为零。
- [x] 运行 `npm test -- --run` 与 `npm run build`，再运行差异格式和密钥忽略检查。
- [x] 启动本地服务，检查健康接口、经典旧记录和新纳甲记录；不点击或调用解释接口。
- [x] 仅提交 `zhouyi/**`、本设计/计划与项目注册表相关变化，提交信息使用中文，不包含工作区其他修改。
