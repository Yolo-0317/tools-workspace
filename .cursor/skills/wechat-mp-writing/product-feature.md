# 牛马也智能 · 返佣单品推荐稿

适用：用户手动要求围绕一件公众号返佣商品写独立推荐稿。稿型为 `product_feature`，不进入定时批次，不改普通长文的返佣禁令。正文由当前 Codex 研究与撰写；不沿用用户主动热点和文学稿的 DeepSeek 手工交接。

生活化正文写法先读 [wechat-mp-native-ad-writing](../wechat-mp-native-ad-writing/SKILL.md)；本页负责选品、事实、结构化交接和草稿预检。

## 先找畅销候选，再决定写哪件

从 `wechat_mp_product` 已跑通的 Select 接口读取候选。默认只在零食与日用小百货中采样，使用零食、早餐面包、纸巾、洗洁精、垃圾袋、收纳用品等需求词，每词最多两页；排除书籍、小家电及其他无关品类。先按来源平台销量提示寻找本次采样内领先的商品，再看预计单笔佣金、读者需求和可核实的商品资料。排除销量提示低于 1000、价格或佣金缺失、佣金金额与比例明显矛盾的商品。`sales_on_flow` 为 0 或缺失时，不称「公众号流量主最畅销」；跨来源销量提示也可能不同口径。报告必须列出采样范围和销量字段，不把本次采样榜伪装成全站热榜或真实成交证明。

每篇只选一件。Agent 要说明销量领先候选中为什么选它，为什么暂不选其他高销量商品。去品牌官网、官方店或当前销售平台商品页核对规格、功能、适用条件、售后和现价；商品标题与 Select 摘要只提供检索线索。不能把平台销量提示写成「全网卖出多少件」。预计佣金只用于内部选品，不出现在正文。

## 写法与推荐边界

每件商品先准备三种不同的标题、开头与切入角度，在本地记录，再用 [wechat-mp-native-ad-writing](../wechat-mp-native-ad-writing/SKILL.md) 写完整稿。该 Skill 负责生活场景、轻包袱、口语节奏和自然引出商品；本页继续约束事实核验与独立草稿流程。

终稿需有明确推荐倾向，并说明商品哪项可核实事实与读者需求相合。简洁交代替代办法、不适合人群与实时价格核对。不能虚构亲测、夸大功效、承诺最低价或编造稀缺性。商品卡前由渲染器单独加入「广告」标识；正文不念返佣机制，预计佣金只保留在内部选品记录。

## 沿用热点稿的通用编辑门禁

成稿前按 [essay-commentary-craft.md](essay-commentary-craft.md) 和 [editorial-evidence-gate.md](editorial-evidence-gate.md) 中适用于消费稿的原则审一遍。先明确「替谁问、他最想问什么、全文只回答哪一个判断」，再检查每段是否带来新事实、新选择标准或新的适用边界。标题承诺要在开头和正文兑现，不能编造某个读者的经历、对话或共同心声。商品参数是平台或品牌的说法时写清出处；价格、库存等快照带查询日期。把限制放进实际使用情境，不把事实边界写成一串审稿说明。逐段朗读，删掉同义复述、清单腔、套话和过密的反问。

交接 JSON 必须增加 `editorial_review`：`target_reader`（具体读者）、`reader_question`（真实问题）、`core_judgment`（唯一核心判断）、`body_anchor`（正文里承载判断的原句片段）及与自然段逐一对应的 `paragraph_roles`（每段的信息或判断增量）。预检复用热点稿的公开文案扫描，拦截编辑指令泄漏、夸张标题、重复段落和清单格式；同时核对正文锚点与逐段记录。机器只能核对可判定的字段，仍须人工判断文章是否真的顺着一个问题向前走。

商品稿不沿用热点事件的三个来源域数量、事件开头、结尾必须设问、900—1100 字或 DeepSeek 双确认要求。商品事实优先回到当前平台商品页和品牌原始资料，同源转载不能充当独立印证。广告披露属于必须保留的商业信息，由独立标识紧贴商品卡呈现。

上述写法借鉴[微信广告流量主成长营](https://training.tencentads.com/uploads/202406/44FVgzA9_zjy5jV.pdf)关于商品相关性与转化的建议、[京东内容原创平台指南](https://wq.360buyimg.com/data/ppms/movie/neirongyuanchuangpingtai-help-20170303.1.pdf)中从具体使用主题自然引出工具的案例。只学表达与结构，不复制原文或借用他人的销量成果。

## 交接与草稿

在 `stock-ai/` 运行：

```bash
.venv/bin/python -m scripts.tools.wechat_mp_draft --kind product_feature --dry-run
```

命令只读查询并打印候选请求。Codex 从中选一件，浏览核对商品事实后在忽略目录 `output/` 写结构化 JSON，字段必须包含：`product_id`、`search_keyword`、`warehouse_id`、`source_name`、`product_name`、`price_yuan`、`commission_yuan`、`queried_at`、`title`、`digest`、`body`、`reader_need`、`alternative`、`not_for`、`source_urls`、`fact_checks`、`editorial_review` 和 `copy_variants`。摘要按 UTF-8 计算不得超过 128 字节，避免草稿 API 摘要被截在半句。`copy_variants` 至少三项，每项含不同的 `angle`、`title` 和 `opening`，终稿标题须对应其中一项。`fact_checks` 的每项为 `{"claim": "正文原句片段", "source_url": "https://..."}`；来源必须在 `source_urls` 中，且人工核对该链接确实支持该条主张。内部 `selection_report` 可记录销量口径、采样范围和未入选理由，不进入公开正文。

写入草稿前还要设置 `cover_asset_path`，指向 `stock-ai/assets/wechat_mp/` 中与商品品类相符、已核对可用的 JPG/PNG 素材。商品入口旁的独立说明会标明「封面为场景示意图」；正文不必重复解释封面。缺少合格封面时停止写入。

```bash
.venv/bin/python -m scripts.tools.wechat_mp_draft \
  --kind product_feature --codex-draft output/product_feature_codex.json --dry-run
```

预检重新查询同一商品，检查价格和预计佣金、文章事实绑定、推广披露、唯一商品卡与标题摘要。`--dry-run` 默认只打印正文，不展示完整 HTML；预检通过仍须由程序确认 HTML 中已插入商品卡。取得用户写草稿的明确要求后去掉 `--dry-run`，构建器将独立「广告」标识和 `<mp-common-cpsad>` 返佣卡直接写进草稿正文 HTML，只更新 `product_feature` 槽位。写入后回读公众号草稿，确认恰好一张卡、`data-pid` 对应所选商品且卡片前有「广告」标识；任一项失败，保留旧槽位草稿。最终发表由用户在公众号后台处理，命令拒绝 `--publish`。
