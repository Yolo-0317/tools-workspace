# Codex 公众号自动取图与原创补图设计

## 目标

让热点长图文 `hotspot` 与贴图 `newspic` 落实同一条图片规则：先从同题公开报道页获取合格图片；数量不足时，程序生成结构化的 Codex 补图请求，Codex 只为缺少的图位生成原创新闻插画，落盘后重跑原入口即可继续质量门禁和微信公众号草稿写入。

## 约束

- 不接入 Composer，也不在 Python 中新增 OpenAI 图片 API、密钥或计费链路。
- Python 负责联网搜图、图片筛选、缺口计算、来源清单和发布门禁；Codex 负责调用可用的 ImageGen 工具。
- 报道图优先，原创图只补缺口，不覆盖已找到的报道图。
- 原创图不得伪造现场、当事人身份、机构标识、伤亡数字或未经证实的细节。
- 保留贴图现有 `--images --image-sources` 手工模式，避免破坏既有调用。
- 生成的图片、来源清单、补图请求均位于现有忽略的素材输出目录，不提交仓库。

## 方案

新增一个无发布职责的图片素材协调模块。它复用 `wechat_mp_discussion_figures` 的同题报道抓取器，把报道图元数据转换成公众号统一来源记录；再扫描约定名称的原创图片，按“报道图在前、原创图补尾”的顺序组成最终素材集。

当数量不足时，协调模块写出 `codex-image-request.json`，内容包括稿型、主题、目标数量、已有报道图数量、缺失图位、每个图位的提示词、目标文件名和安全限制，并抛出带请求文件路径的专用异常。CLI 将该异常作为可恢复状态输出，禁止上传不完整草稿。

Codex 读取请求后逐项调用 ImageGen，将结果保存为指定文件。再次执行相同命令时，协调模块识别这些文件为 `source_type=original`，写入 `image-sources.json`，随后进入原有上传或长图文渲染流程。

## 文件与接口

### `scripts/tools/wechat_mp_codex_images.py`

负责统一素材协议，公开：

- `CodexImageGenerationRequired`：包含请求文件路径和缺失数量。
- `prepare_newspic_topic_images(topic, research_urls, target_count) -> PreparedTopicImages`：获取贴图所需图片，完整时返回图片路径和来源清单路径，不足时写请求并抛异常。
- `prepare_hotspot_topic_images(topic, body_count=3) -> None`：在长图文注图前完成联网取图和缺口检查；封面目标为 `cover.jpg`，正文原创补位目标为 `manual-01.jpg` 至 `manual-03.jpg`。
- `write_image_generation_request(...) -> Path`：生成稳定、可测试的 Codex 请求 JSON。

该模块不上传图片，不调用微信公众号 API，不调用任何模型。

### 贴图 CLI

`wechat_mp_newspic_draft.py` 增加自动素材模式：

```bash
uv run python -m scripts.tools.wechat_mp_newspic_draft \
  --slot newspic_hotspot \
  --title "具体事件为什么引发争议？" \
  --content output/newspic_copy.txt \
  --topic "具体事件检索词" \
  --research-url https://example.com/report
```

- `--topic` 与 `--images` 二选一。
- 自动模式默认目标 6 图，可用 `--image-count 6..9` 调整。
- `--research-url` 可重复，作为优先报道来源。
- 自动模式由程序生成 `image-sources.json`，不再要求用户传 `--image-sources`。
- 手工模式继续要求 `--images` 与 `--image-sources` 同时出现。
- `--dry-run` 完成图片、来源和内容校验，但不调用微信公众号上传接口。

### 长图文入口

`build_hotspot_article` 在现有 `inject_discussion_figures` 之前调用 `prepare_hotspot_topic_images`。准备函数先运行现有报道图检索：

1. 有合格报道图时，现有逻辑从报道图裁出封面，并选取与封面不重复的正文图。
2. 正文不足 3 图时，请求缺少数量的 `manual-NN.jpg`。
3. 完全没有可用报道图且无封面时，同时请求 `cover.jpg` 和正文缺图。
4. 生成文件存在后，现有 `ensure_discussion_cover` 与 `ensure_discussion_body_figures` 继续完成门禁和图注。

这同时覆盖旧自动热点入口与 `--codex-draft` 入口，不改变正文生成方式。

## 请求 JSON

示例：

```json
{
  "schema_version": 1,
  "article_type": "newspic",
  "topic": "具体事件检索词",
  "target_count": 6,
  "report_image_count": 4,
  "missing_count": 2,
  "safety_rules": [
    "原创新闻插画，不得伪造新闻现场",
    "不得添加可识别真实人物、机构标识、伤亡数字或未经证实的细节",
    "画面中不得出现文字、二维码、水印或品牌标识"
  ],
  "slots": [
    {
      "slot": "scene-05",
      "output_path": "/absolute/path/manual-01.jpg",
      "prompt": "……"
    }
  ]
}
```

所有 `output_path` 使用绝对路径，避免 Codex 保存到错误工作目录。提示词包含主题、稿型分镜作用、横竖构图和统一安全约束，但不把未经证实的事实写进画面。

## 来源清单

贴图自动模式生成的 `image-sources.json` 继续使用现有校验契约：

- 报道图：`source_type=report`、`page_url`、`page_title`。
- 原创图：`source_type=original`、`fallback_reason`，固定说明公开报道图不足，由 Codex 原创补位。

长图文沿用现有图注：报道图为“图源：公开报道（引用）”，原创图为“原创新闻插画”。

## 错误处理

- 网络抓图失败不静默降级为品牌图，而是进入原创补图请求。
- 请求文件已生成但目标文件仍缺失时，每次重跑覆盖请求，确保缺口与当前素材一致。
- 原创文件尺寸、格式或文件大小未通过现有门禁时仍视为缺失，并在请求中保留该图位。
- 自动贴图不足目标数量时，不上传任何图片，不调用草稿 API。
- 参数组合错误在联网和远端调用前失败。

## 测试与验收

1. 单元测试证明贴图自动模式优先返回报道图，并为不足图位生成请求。
2. 单元测试证明指定的 `manual-*` 文件出现后能补齐图片，并生成完整来源清单。
3. 单元测试证明长图文缺正文图或封面时生成正确请求，补齐后不再抛异常。
4. CLI 测试覆盖自动模式、手工兼容模式和非法参数组合。
5. 聚焦公众号测试、Python 编译、CLI `--help` 与一次不调用微信 API 的素材准备演练均通过。
