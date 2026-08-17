# 公众号 Codex 唯一写稿后端设计

## 目标

将「牛马也智能」公众号的所有 AI 写稿与 AI 改稿统一到本机 Codex CLI。公众号流水线不得再调用 DeepSeek API、Cursor Agent 或 Composer 生成、扩写、压缩、改写公开正文。东财选股、投资分析和 SOP 并发终审不在本次范围内，继续使用各自现有后端。

## 当前问题

公众号目前存在三条并不一致的写作路径：

1. `hotspot`、`hot_business`、`silver`、`short_drama_feature` 已支持人工准备的 `--codex-draft` JSON，但不传该参数时仍可能走旧生成器。
2. 影视、市场、板块、龙虎榜、Top5 等模块通过 `call_wechat_mp_llm` 调用 Cursor Agent，默认模型是 `composer-2.5`。因此《牛来》虽然由 Codex 完成选题设计和剧情锚点，最终正文仍不能证明是 Codex 全程生成。
3. 要闻的十条 AI 点评绕过公众号统一入口，固定调用 DeepSeek API。

仅修改 `LLM_BACKEND` 环境变量无法覆盖第二、第三条路径，也无法阻止失败后静默回退。

## 方案

采用“统一入口、Codex 执行、失败关闭”的方案。

### 统一调用入口

保留现有 `call_wechat_mp_llm(messages, ...)` 作为公众号模块的稳定接口，但将其底层实现改为独立的 Codex 客户端。客户端使用本机 `codex exec` 非交互运行，并把消息转换成单次写作提示。

公众号模块不得直接调用 `call_deepseek`、`call_cursor_agent` 或自行读取 `LLM_BACKEND`。现有调用者分批迁移到统一入口，至少覆盖：

- 热点深评、热点商业、银发内容；
- 影视长文、短剧专题；
- 市场、板块、龙虎榜、Top5 和要闻点评；
- 其他进入「牛马也智能」草稿槽位的 AI 成稿、扩写、压缩和重写步骤。

纯数据采集、规则排版、图片处理、短剧选择和确定性模板不属于 AI 写稿，可保持现状。

### Codex 客户端

新增专用客户端，职责限定为：

1. 定位 `codex` 可执行文件，优先使用显式配置，其次使用 `PATH`。
2. 在最小化的公众号写作工作目录中运行 `codex exec --ephemeral`，避免加载投资分析上下文。
3. 默认使用当前 Codex 配置的模型；如设置公众号专用模型，只接受 `WECHAT_MP_CODEX_MODEL`，不复用 Cursor 或 DeepSeek 的模型变量。
4. 支持超时、有限重试和最后回复提取；结构化生成场景可传 JSON Schema。
5. 不把 Cookie、Token、`wxTicket`、`.env` 内容或其他凭据写入提示、日志和结果文件。

现有 `--codex-draft` 路径继续保留：用户交互式要求写稿时，当前 Codex 研究并产出本地结构化 JSON；定时任务或无需人工确认的生成步骤由同一个 Codex 客户端完成。

### 失败关闭

公众号写稿不设置备用模型。出现以下情况时必须停止当前稿件，不写入或覆盖微信草稿：

- Codex CLI 不存在、未登录或返回非零状态；
- 超时或重试耗尽；
- 返回空正文、无效 JSON 或未通过现有质量门禁；
- 检测到调用者试图为公众号指定 `deepseek`、`cursor` 或 `composer`。

错误信息只说明 Codex 未就绪及安全的排查方式，不提示配置 DeepSeek 作为替代。

### 生成来源证明

每次公众号 AI 调用返回正文的同时，在进程内记录生成来源：

- `provider=codex`
- Codex CLI 版本
- 调用模式：`interactive_draft` 或 `codex_exec`
- 生成时间和稿件 kind

写入微信草稿前增加来源门禁：只要本篇包含 AI 生成步骤，就必须能汇总出全链路均为 `codex`；缺失来源或出现其他 provider 时拒绝推送。公开正文不展示该内部信息。

本地诊断记录不得保存完整提示、正文、登录信息或私有链接，只保存上述最小元数据与结果状态。

## 兼容与配置

- `SOP_LLM_BACKEND=deepseek` 及东财 SOP 调用保持不变。
- 通用投资分析中的 `LLM_BACKEND` 暂不修改，避免扩大影响范围。
- 公众号新增 `WECHAT_MP_CODEX_COMMAND`、`WECHAT_MP_CODEX_MODEL`、`WECHAT_MP_CODEX_TIMEOUT_SECONDS` 和 `WECHAT_MP_CODEX_MAX_RETRIES`；均有安全默认值，命令配置只接受可执行文件路径，不接受拼接 shell 字符串。
- 旧的 `WECHAT_MP_LLM_MODEL`、`WECHAT_MP_CURSOR_*` 和 `WECHAT_MP_NEWS_AI_BACKEND` 对公众号写作不再生效，并在文档中标为废弃；如配置为非 Codex，不兼容运行而非回退。
- 对外 CLI 参数和微信草稿槽位保持兼容，已有 `--codex-draft` JSON 格式不变。

## 测试与验收

先写失败测试，再实现迁移。验收至少包括：

1. `call_wechat_mp_llm` 只调用 Codex 客户端，不触发 Cursor Agent 或 DeepSeek HTTP。
2. 要闻 AI 点评改走公众号统一入口。
3. Codex 不可用、超时、返回空值或非法结构时，流程在微信 API 调用前失败。
4. `--codex-draft` 的热点、热点商业、银发和短剧专题继续通过既有校验。
5. 影视稿的生成与二次重写均留下 Codex 来源，避免再出现《牛来》式“方向由 Codex 完成、正文后端不可证明”的情况。
6. 定时市场、板块、龙虎榜、Top5 和要闻任务在 Codex 可用时保持原有输出结构；Codex 不可用时不创建低质量模板稿冒充 AI 稿。
7. 东财 SOP 测试仍断言 `SOP_LLM_BACKEND=deepseek`，证明未被公众号改造影响。
8. 文档、示例环境变量和公众号技能说明统一写明“公众号 AI 写稿只用 Codex，失败不回退”。

完成后运行公众号 LLM 分流、各文章生成器、草稿 CLI 与东财 SOP 分流的相关单元测试，并执行一次不调用微信写入接口的公众号干跑验证。

## 非目标

- 不把东财选股、投资分析或 SOP 改成 Codex。
- 不改变公众号选题策略、公开图来源、原创度、完读率、短剧归因和草稿槽位规则。
- 不自动发表文章。
- 不清理当前工作区中与本功能无关的既有修改或素材删除。
