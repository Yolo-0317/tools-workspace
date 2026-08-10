# 牛津树听读 / 带读 — 架构与约定

面向 Agent 与维护者的**运行时真源**。课文数据见 `backend/teaching/ort_oxford_owl/README.md`。

## 1. 数据管线

| 文件 | 用途 |
|------|------|
| `backend/teaching/ort_oxford_owl/books.json` | **真源**：扁平 `lines[]` + 按页 `pages[].lines` + `image` |
| `backend/teaching/ort_oxford_owl/ort_l3_page_groups.json` | L3 分页人工对齐参考（改 `books.json` 时对照） |
| `backend/teaching/ort_oxford_owl/ort_l4_page_groups.json` | L4 分页（`apply_ort_pdf_page_groups.py --level 4` 生成） |
| `backend/teaching/lessons.json` | 内置 lesson（`flatten_lines(pages)` → `\n` 拼接） |
| `backend/teaching/ort_oxford_owl/catalog.json` | 专题 API：`GET /api/ort/catalog` |
| `frontend/public/ort/{book_id}/pNN.jpg` | 页图；缺图则专题不展示该读本 |

```bash
# 改 books.json 后
cd english-buddy/backend && python3 teaching/build_lessons_v5.py
cd .. && ./scripts/restart.sh
```

`catalog.py`：`books.json` 比 `catalog.json` 新时会打 warning 日志。

### 同页多句

书上同一插图页可有多行文本（例：L3 Sniff p06 两句）。在 `books.json` 里写入：

```json
{
  "lines": [
    "Sniff liked to roll on her back.",
    "She jumped up for a stick."
  ],
  "image": "ort_sniff/p06.jpg"
}
```

`lines[]` 顺序 = 带读顺序；`flatten_lines` 与 `ortLinePageIndex` 据此映射 global line index。

## 2. 入口与模式

| 入口 | 听读 | 带读 |
|------|------|------|
| 专题 `OrtTopicView` | 「听读」→ `ortSessionListenOnly=true` | STT 账号「开始跟读」 |
| 首页选 ORT 课 | 非 STT 账号 / 无麦 | STT 账号 + 麦克风 |
| 未登录 | 听读 | — |

账号：`ENGLISH_BUDDY_STT_USERS`（见 `docs/AUTH.md`）。听读时 `set_stt_active: false`；带读需 HTTPS 麦克风。

## 3. 运行时状态

```text
                    WebSocket /ws/call
前端                ──────────────────              后端
readAlongLineIndex  ←  assistant_text.line_index   ReadAlongState.index
                    ←  (chunk 与 material line 映射)
ortViewPageIndex    ←  TTS onplaying / 手动翻页     （无独立 server 字段）
ortScriptLines      =  当前 line 所在页全部句子      pages[].lines
```

### 前端（`useVoiceCallWs.ts`）

| 符号 | 含义 |
|------|------|
| `readAlongLineIndex` | 服务端 material line；跟 `assistant_text` |
| `ortViewPageIndex` | 插图页；自动在 **TTS 起播** 对齐；滑动翻页立即更新 |
| `ortScriptPageIndex` | `ortLinePageIndex(book, readAlongLineIndex)` |
| `teacherPlaybackEpoch` | 本地打断/翻页递增；旧 TTS `finally` 不 handoff |
| `serverPlaybackGeneration` | 跟 `assistant_text.playback_generation`；发给 `teacher_playback_done` |

常量（`frontend/src/config/call.ts`）：`POST_TTS_LISTEN_GRACE_MS=950`，`ORT_LISTEN_PAGE_TURN_MS=120`；纯插图页停留优先跟上一句 TTS 实际播放时长（`lastTeacherSpeechMs`），兜底 `ORT_ILLUSTRATION_PAGE_MS=2200`，钳制 `ORT_ILLUSTRATION_DWELL_MIN_MS`～`MAX_MS`。

### 后端（`ws_call.py` + `read_along.py`）

| 符号 | 含义 |
|------|------|
| `turn_lock` | 串行 index / utterance 准备阶段 |
| `listen_only_busy` | 听读自动跳下一句进行中 |
| `listen_only_hold_after_teacher` | 手动「下一句/点句」后暂停一次自动读 |
| `reread_in_progress` | 重读/翻页进行中，阻塞 auto-advance |
| `playback_generation` | 单调递增；`interrupt` 也递增；校验 `teacher_playback_done` |
| `child_spoken_buffer` | STT 多段合并；`is_sufficient_child_attempt` 不足则继续听 |
| `utterance_queued` | STT 处理中又收到 `utterance_end` 时排队重试 |

长句（>10 词）拆多个 **chunk**；带读逐步念 chunk。开场/重读整句用 `material_line_text()`；多 chunk 合并朗读时 TTS `chunk_index=None`（现场合成）。

**TTS 在锁外**：`_prepare_read_along_child_turn`（持锁）→ `_deliver_teacher_read_along`（锁外合成播放）。

## 4. 流程

### 带读（STT）

1. 老师念当前 chunk → `assistant_text` + `tts_audio`
2. 客户端 `onplaying` → 插图同步；播完 → `scheduleListenAfterTeacher` → 叮叮
3. 孩子说话 / 「我说完啦」→ `utterance_end` → 发音评分（不阻塞）→ 下一句
4. 跟读不完整：累积 buffer，提示「继续说这一句…」，不跳下一句

### 听读（listen-only）

1. 老师念 chunk
2. 播完 → 若本页末句且后续有纯插图页 → `dwellOrtIllustrationPages` 停留展示
3. `teacher_playback_done`（带 `playback_generation`）→ `_continue_listen_only` → 下一句
4. **滑动翻页**：`reread_line` + `resume_listen_auto:true` → 念该页首句后继续自动读
5. **下一句按钮**：设 `listen_only_hold`，需再点或等下一轮 handoff

## 5. WebSocket 消息（ORT 相关）

| C→S | 说明 |
|-----|------|
| `start_call` | `lesson_id=ort_*`，`mode=read_along`，`tts_speed` |
| `reread_line` | `line_index`；听读翻页加 `resume_listen_auto:true` |
| `teacher_playback_done` | 听读播完；**必须**带 `playback_generation` |
| `read_along_advance` | 「下一句」；听读会 hold |
| `set_stt_active` | 听读入口发 `{enabled:false}` |
| `interrupt` | 打断老师；服务端递增 `playback_generation` |

| S→C | 说明 |
|-----|------|
| `assistant_text` | `text`，`line_index`，`playback_generation` |
| `tts_audio` / `tts_end` | 客户端负责播完时机 |
| `reread_line` | 重读确认；**仅** `ttsPlaying` 时前端切 speaking |
| `lesson_complete` | 本篇读完 |
| `pronunciation_result` | 带读评分（听读可忽略） |

## 6. UI（`CallView.vue`）

- ORT 通话：`call-screen--ort`；手机一屏布局，插图 `flex:1`
- 「本页句子」：同页多句**全部展示**（`script-panel--ort` 不限 `max-height`）
- 左右滑动翻页（阈值 48px）；纯插图页提示「本页纯插图」
- 带读：暂停 / 上一句 / 再说一遍 / 我说完啦 / 下一句
- 听读：老师自动往下读；滑动翻页后继续自动读

## 7. 常见故障

| 现象 | 排查 |
|------|------|
| 同页只显示一句 | `books.json` 该页 `lines` 是否多句；是否跑 `build_lessons_v5.py` |
| 第二句被裁切 | `script-panel__lines` 是否误设 `max-height` |
| 听读翻页后停 | `resume_listen_auto`；`listen_only_hold` |
| 图比语音快 | 插图须在 TTS `onplaying` 更新，勿在 `assistant_text` 翻页 |
| 图比语音慢 | 大图解码；可预加载 `preloadOrtAroundLine` |
| 带读卡住 speaking | 服务端 `reread_line` 在 TTS 结束后勿强制 speaking |
| 听读连跳两句 | `playback_generation` 是否与 `assistant_text` 一致 |
| 专题与通话课文不一致 | `catalog.json` 是否过期 |

## 8. 相关代码

| 区域 | 路径 |
|------|------|
| 通话状态机 | `frontend/src/composables/useVoiceCallWs.ts` |
| 通话 UI | `frontend/src/views/CallView.vue` |
| 专题 | `frontend/src/views/OrtTopicView.vue` |
| line↔page | `frontend/src/utils/ortPage.ts` |
| WS 后端 | `backend/ws_call.py` |
| 课文状态 | `backend/services/read_along.py` |
| ORT API | `backend/routers/ort_api.py` |
