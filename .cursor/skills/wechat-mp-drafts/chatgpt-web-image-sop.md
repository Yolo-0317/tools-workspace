# ChatGPT 网页原创配图 SOP

## 适用范围

- 原创小说、栀夏生活分享和用户明确同意原创配图的文章。
- 热点、影视和公共事件先找可追溯的官方或媒体图片；数量不足可以少配，不为凑数启动生图。
- 用户明确指定“用 Codex 生成图片”时，当前任务临时改用内置 ImageGen，本 SOP 暂停，不改变后续默认值。

## 前置检查

1. 当前 Chrome 已登录 `chatgpt.com`，目标图片会话处于当前标签。
2. 读取 `codex-image-request.json` 的 `slots`、`safety_rules`、`generator` 和 `failure_policy`。
3. `generator` 必须是 `chatgpt_web`，`failure_policy` 必须是 `stop_and_prompt`。
4. 不读取 Cookie、密码、localStorage、sessionStorage，不尝试自动登录。

## 分镜与请求字段

Codex 在生成前逐槽核对：

- `slot_id`：稳定槽位名，如 `cover`、`body-01`。
- `output_path`：请求目录内的绝对路径。
- `prompt`：画面主体、动作、场景、光线、构图、比例和禁止项。
- `reference_slot_id`：需要同一人物或画风时指向 `cover`。
- `safety_rules`：不得伪造新闻现场、真实人物或未经核实细节，画面不含文字、二维码和水印。

先生成封面。封面是本组人物脸型、发型、年龄感、体型、色调和画风的基准；后续人物图通过 OpenCLI `browser upload` 上传封面或正式角色母版作为参考图。

## 执行

```bash
cd stock-ai
PYTHONPATH=. python -m scripts.tools.wechat_mp_chatgpt_images \
  --request /absolute/path/codex-image-request.json \
  --download-dir /Users/huan.yu/Downloads
```

执行器逐槽完成：绑定当前标签、检查登录态、上传参考图、输入提示词、等待新图片、打开新图片、点击“保存”、等待下载完成、机械质检并原子写入目标路径。结束只解除 OpenCLI 绑定，不关闭 ChatGPT 标签。

## 质检

机械质检：文件可解码、大小不低于门槛、宽高不低于门槛、比例符合封面/正文槽位、临时文件完整后才替换目标图。

Codex 必须查看本地图并做视觉质检：

- 同一人物的脸型、五官、发色、发型、年龄感和体型是否稳定；
- 同一段情节的服装、饰品、道具、时间、光线与场景锚点是否连续；
- 手指、耳朵、鞋、衣物边缘是否存在明显生成错误；
- 是否出现意外文字、品牌、二维码、水印或疑似真实新闻截图；
- 每张图是否承担不同叙事功能，而非换角度重复。

任一项不通过，只重做对应槽位，不带病插入草稿。

## 失败与恢复

登录、标签页、生成、保存、下载或质检任一步失败：立即停止，向用户说明需要登录、切换标签或检查页面后重试。禁止自动切换 Codex ImageGen、DeepSeek 或其他平台。

进度写入请求目录的 `chatgpt-image-progress.json`。重试时跳过已有合格目标图，从第一个未完成槽位继续；参考槽位未完成时不得生成依赖图。

## 插入草稿前

- 所有必需槽位已完成，或用户明确接受减少图片数量。
- Codex 已逐张查看并确认人物及叙事连续性。
- 公开报道图保留可追溯来源；原创图按稿型保留 AI 生成披露。
- 重跑原草稿命令不再返回补图请求，才允许上传微信草稿箱。
