# 中老年健康稿：微信草稿 API

只在用户明确要求把已审正文写入草稿箱时使用。优先复用 `stock-ai/scripts/tools/wechat_mp_client.py` 的官方 API 客户端；公众号后台页面 URL 中的 `token` 是页面会话参数，不是 API `access_token`。避免为 API 草稿操作先打开后台编辑页。

## 写入顺序

1. 保留成稿、两张本地图片、图源及授权记录。按[健康稿排版](../../wechat-mp-health-content/layout.md)生成带内联样式的 HTML 和手机预览；不要用旧的纯段落渲染覆盖已美化版式。检查标题、段落、图片位置、蓝色高亮、文末图片来源和结尾关注句。封面可与正文首图相同。
2. 调用 `verify_required_wechat_egress()` 强刷 API token，验证当前出口。不要把凭据、token 或完整带凭据 URL 打到日志里。`40164` 是微信白名单问题；本地 `-2` 是请求网络异常，先诊断 DNS、路由与当前执行环境，不能把它说成白名单错误。
3. 用 `upload_article_image(path)` 上传正文图片，取得正文可用的图片 URL；用 `add_permanent_image(cover)` 取得封面 `thumb_media_id`。HTML 文末设置“图片来源”，逐条注明对应图片，保留作者、原图与许可链接，使用 14px 灰色文字。
4. 首次用 `draft_add(articles=[article])`；修改已建草稿用 `draft_update(media_id=..., article=...)`，沿用原 `media_id`、封面和图片素材。记录 `media_id` 与本地稿件对应关系，防止回读失败后重复创建。这里只进草稿箱，不调用发表接口。
5. 用 `fetch_draft_news_item(media_id=...)` 回读。核对标题、正文首尾、两张图片的身份及顺序、文末与各图对应的小字来源、蓝色高亮、分节标题、重点框及列表的主要样式、结尾关注句。微信可能把正文图片 URL 从 `http … /0` 改为 `https … /640`；按图片资源路径或素材身份比较，不要求 URL 逐字一致。回读异常时查具体字段，已取得 `media_id` 就不要再 `draft_add`。

## 本次故障留下的判断

- 单独取得新 `access_token` 不等于写稿脚本的网络权限已就绪。曾出现只读 `python -c` 请求成功，而仓库脚本因 DNS `socket.gaierror` 在预检阶段返回 `-2`；正式网络授权下的只读路由探针成功后，原 API 推稿流程才走通。遇到同类现象，先定位失败层，并按当前环境的正式权限流程处理，不关闭预检或换命令形式规避限制。
- 草稿 API 返回 `media_id` 后，即便本地核验脚本报错，草稿也可能已经创建。先回读该 ID；本次误报是图片 URL 的协议与尺寸被微信规范化。只有核实草稿确实不存在，才考虑新建。
- 本次封面同时放在正文，两张真实图分别在图下署名；两处重点使用 `#1a5276`。修订图源、颜色和关注句时，使用 `draft_update` 更新同一草稿并逐项回读，没有重新上传图片或新建草稿。

- 2026-09-30 两篇草稿回读的 `thumb_media_id` 为空，但原永久封面素材仍有效；把空值原样传给 `draft_update` 会返回 `40007 invalid media_id`。更新前核对封面 ID：回读为空时，先验证本地 `push_record.json` 的原 `cover_media_id` 是否有效，再使用该 ID。回读可按非空 ID 或 `thumb_url` 的素材资源身份核验，不重新创建草稿。
