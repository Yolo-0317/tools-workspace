# 公众号长文短剧推广组件设计

**日期：** 2026-08-16

**账号：** 牛马也智能

**状态：** 用户已确认设计，待实现计划

## 目标

将公众号所有长图文中的普通返佣商品推广替换为短剧推广。程序在每次生成草稿时从微信内容推广短剧列表获取有效候选，按正文相关度、热度和分佣比例选择一部，在正文约三分之二处插入一个短剧组件。任何异常都不得回退为普通返佣商品。

## 适用范围

适用稿型为 `hotspot`、`tv_review`、`tv`、`film`、`movie`、`sector`、`market`、`news`、`top5`、`dragons`、`workspace` 和 `temp`。

不处理以下内容：

- `newspic`、栀夏生活贴图和小绿书；
- 已搁置的简选带货稿与 `commerce`；
- 微信自动流量主广告位，本文只调整人工插入的内容推广组件。

每篇长文只插入一个短剧组件。组件位于正文约三分之二处，按完整段落或区块边界对齐，并避开剧透预警、首屏正文、互动引导与免责声明。

## 已核验的接口与组件结构

短剧列表接口为：

```text
POST https://daihuo.qq.com/trpc.cps.weixin_select.WeiXinSelect/DramaSelect
```

请求结构：

```json
{
  "flow_type": 3,
  "query": {},
  "page": {"no": 1, "size": 10},
  "kol_info": {"id": "${WECHAT_MP_DRAMA_KOL_ID}"}
}
```

账号标识必须来自本地环境变量，不得写入仓库。接口已核验返回 `ret=0`、`total` 和 `recommend_list`；2026-08-16 实测共有 2145 部候选。单条候选可提供 `drama_id`、`drama_name`、`src_appid`、`play_appid`、`cover_url`、`era`、`theme`、`desc`、`status`、`plan_id`、`rate`、`hot_degree`、`media_count`、`real_offline_time`、`preview_path`、`preview_sn`、`trace_id` 关联信息及曝光/点击 URL。

微信草稿中人工插入的短剧使用：

```html
<mp-common-cpsad data-pluginname="mpcps" data-adtype="short-play" ...></mp-common-cpsad>
```

短剧与普通商品共用 `mp-common-cpsad` 标签，但必须通过 `data-adtype="short-play"` 区分。短剧草稿没有 `product_info.footer_product_info`，因此不得继续调用普通商品的 `getcardinfo` 或写入 footer product key。

## 数据模型与缓存

新增短剧候选模型，至少保存：

- `drama_id`、`drama_name`、`era`、`theme`、`desc`；
- `src_appid`、`play_appid`、`plan_id`；
- `cover_url`、`media_count`、`preview_path`、`preview_sn`；
- `rate`、`hot_degree`、`status`、`real_offline_time`；
- 列表响应的 `trace_id` 与抓取时间。

缓存只保存接口返回的业务字段和时间戳，不保存 Cookie、Authorization、公众号 access token、编辑页 token 或完整请求头。缓存有效期默认六小时；程序可在到期前主动刷新，刷新失败时只允许继续使用尚未到期的缓存，已经到期则失败关闭。

## 候选过滤与去重

候选必须同时满足：

- `status == 1`；
- 剧名、`drama_id`、来源应用、播放应用、推广计划、封面和播放路径完整；
- 下线时间距离当前时间不少于七天；
- 集数大于零；
- 分佣比例大于零。

同名短剧可能对应不同 `drama_id` 和推广计划。去重以规范化剧名为键，只保留一条，依次比较：

1. 分佣比例更高；
2. 下线时间更晚；
3. 热度更高；
4. `drama_id` 字符串排序，确保结果稳定。

## 内容匹配与轮换

每篇文章生成用于匹配的文本，由标题、摘要和正文前 1200 个汉字组成。

短剧排序分数由三部分组成：

- 内容相关度 50%；
- 归一化热度 30%；
- 归一化分佣比例 20%。

内容相关度使用可解释的关键词匹配，不调用写稿模型：

- 影视、社会热点稿匹配剧名、题材、时代和简介中的实体及主题词；
- 财经、市场、科技和工作流稿优先提高“职场、都市、励志”候选的基础相关度；
- 没有明显匹配时，从有效候选的热度前列中稳定轮换，不总是重复第一部。

本地使用记录保存最近插入的短剧。七天内优先避免重复同一 `drama_id`；若有效候选不足，可放宽重复限制，但仍不得选择已过期或无归因信息的条目。

## 组件生成与归因门禁

组件必须包含人工样本中已核验的短剧属性：`data-adtype="short-play"`、短剧元数据、`data-dramaid`、来源应用、播放应用、推广计划、追踪标识和默认播放路径。

人工样本的默认路径包含 `wxTicket`。该字段涉及推广归因，不能把一部短剧的票据复制给另一部短剧，也不能在缺少证据时自行拼接。正式启用自动注入前必须完成以下表征测试：

1. 对一个 `DramaSelect` 候选生成测试组件；
2. 经微信草稿 API 写入测试草稿并重新读取；
3. 确认微信没有剥离 `short-play` 组件及关键属性；
4. 由后台预览确认可以打开正确短剧；
5. 确认跳转携带与该候选推广计划对应的有效归因票据。

只有上述五项全部通过，自动注入才可启用。若 `DramaSelect` 不能直接提供有效归因路径，则继续定位选择短剧时调用的归因/建卡接口；在此之前保持失败关闭，不使用仅能播放而无法确认结算的组件。

每次组件生成使用新的随机 `data-traceid`；不得复用人工样本的追踪 ID。

### 自动归因建卡（2026-08-17 已验证）

公众号编辑器选择短剧时调用：

```text
POST https://mp.weixin.qq.com/cgi-bin/minidrama?action=link
```

表单中的 `cps_detail` 为 JSON 字符串，字段与候选池映射如下：

- `request_id`：调用时生成的毫秒时间戳字符串；
- `biz_type`：固定为 `0`；
- `appid`：候选短剧的 `play_appid`；
- `plan_id`：候选短剧的 `plan_id`；
- `promoter_id`：`WECHAT_MP_DRAMA_KOL_ID`；
- `ext_info`：固定为空字符串。

接口成功响应包含外层 `base_resp.ret=0`，外层 `data` 是一个 JSON 字符串。解析后的内层对象必须满足 `errcode=0`，其 `path` 是 `plugin-private://.../pages/playlet/playlet` 跳转路径，并包含该候选对应的 `dramaId`、`srcAppid` 和非空 `wxTicket`。

自动获取必须逐项验证：响应 `dramaId == drama.drama_id`、响应 `srcAppid == drama.src_appid`，请求 `appid == drama.play_appid`、请求 `plan_id == drama.plan_id`。任一不一致都拒绝建卡，不缓存响应，不尝试替换 ID 或复用其他短剧票据。

该接口依赖公众号后台网页登录态，不是公众号开放 API。认证信息只允许从本地忽略的 JSON 文件读取，文件权限必须为 `0600`。文件只包含非空 `cookie`、后台 `token`、`fingerprint` 和可选 `lang`（默认 `zh_CN`）；Referer 由代码使用 token 构造，不保存完整编辑页 URL。代码、测试夹具、Git、命令行参数和日志不得出现真实认证值。

请求只发送业务必需字段。表单外层包含 `token`、`lang`、`f=json`、`ajax=1`、`fingerprint`、每次新生成的 `random` 和 `cps_detail`；请求头只设置 JSON 接受类型、表单内容类型、`X-Requested-With: XMLHttpRequest`、Cookie 和同源 Referer，不复制 `sec-ch-*`、浏览器版本或其他无关请求头。

登录态过期、外层或内层返回失败、响应结构变化、路径校验失败时保持失败关闭。错误信息只允许包含错误码和可操作提示，不得包含 Cookie、token、`wxTicket`、完整 `path` 或原始响应正文。

成功后把验证过的路径转换为现有 `ShortDramaAttribution`，保存到本地忽略的归因缓存，再沿用组件生成、草稿写入和回读验证链路。正式记录轮换使用仍只能发生在草稿回读成功之后。

## 与现有返佣商品链路的关系

普通返佣商品能力继续保留给已经搁置的独立 `commerce` 工具，但从公众号长文主流水线移除：

- 长文不得调用普通商品自动选品；
- 长文不得生成没有 `data-adtype="short-play"` 的 `mp-common-cpsad`；
- 长文不得写入 `product_info.footer_product_info`；
- `WECHAT_MP_FOOTER_PRODUCT` 即使仍存在，也不能在长文稿型中生效；
- 不允许在短剧失败时回退商品。

新增短剧总开关和配置：

- `WECHAT_MP_SHORT_DRAMA=1`：长文启用短剧推广；
- `WECHAT_MP_DRAMA_KOL_ID`：内容推广账号标识；
- `WECHAT_MP_DRAMA_CACHE_TTL_HOURS=6`：列表缓存时长；
- `WECHAT_MP_DRAMA_MIN_VALID_DAYS=7`：最短剩余有效期；
- `WECHAT_MP_DRAMA_REPEAT_DAYS=7`：重复回避窗口。
- `WECHAT_MP_DRAMA_WEB_SESSION_FILE`：权限为 `0600` 的公众号后台网页会话文件；未配置时不调用自动归因接口。

默认值必须安全：短剧开关未开启时不插任何内容推广组件；开关已开启但配置或归因不完整时阻止写入草稿。

## 数据流

```text
生成长文
  → 读取或刷新 DramaSelect 短剧池
  → 过滤、同名去重
  → 根据文章内容评分并避开近期重复
  → 获取该候选的有效归因参数
  → 在正文约 2/3 的区块边界插入 short-play 组件
  → 草稿前门禁扫描
  → 微信草稿 API
  → 回读草稿验证组件仍存在
```

## 失败处理

以下任一情况必须在微信草稿写入前报错：

- `DramaSelect` 请求失败且没有有效缓存；
- 候选列表为空或全部在七天内下线；
- 短剧关键字段、推广计划或归因票据缺失；
- 生成内容仍含普通返佣商品组件；
- 组件没有 `data-adtype="short-play"`；
- 草稿回读时组件被微信剥离或关键属性发生不兼容变化。

错误信息只显示阶段、剧名、`drama_id` 和缺失字段，不输出账号标识、票据、token 或完整组件 HTML。

## 测试与验收

单元测试覆盖：

- `DramaSelect` 分页和字段解析；
- 状态、下线时间和字段完整性过滤；
- 同名不同计划去重；
- 内容相关度、热度、分佣综合排序；
- 七天重复回避与稳定轮换；
- 组件 HTML 转义、唯一追踪 ID 和正文三分之二定位；
- 所有长文稿型只允许 `short-play`，不得出现普通商品组件或 footer product key；
- `newspic` 和 `commerce` 不受长文短剧规则影响；
- 列表、配置或归因异常时失败关闭。

集成验收分两步：

1. 只生成测试草稿，回读并核验短剧组件、剧名和关键字段；
2. 用户在公众号后台预览并打开短剧，确认剧目正确和推广归因有效后，才允许将短剧开关用于全部长文。

不得用正式文章作为第一次组件结构实验，也不得自动发表测试草稿。
