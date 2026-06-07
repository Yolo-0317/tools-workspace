# 内置课文库（lessons.json v5）

真源文件：`backend/teaching/lessons.json`  
启动时由 `services/lesson_store.py` 按 `version` 字段种子导入 SQLite。`version` 变化时会对比每课 `title`/`text`：**仅改动或删除的课文**清空其 TTS 预热缓存；未改动的课保留已预热音频（自定义课文不受影响）。首次导入仍会全量灌库。

## 结构

| 学段 | grade_id 示例 | 册别 |
|------|---------------|------|
| 幼儿园 | `kg_small` / `kg_middle` / `kg_large` | 小班 / 中班 / 大班 |
| 拓展 | `ort_dialogue` | **牛津阅读树** Biff / Chip / Kipper 家庭对话（原创短句，非 ORT 原文） |
| 小学 | `g1_up` / `g1_down` … `g5_up` / `g5_down` | 按教材真实上、下册 |

规模（v7）：**14** 个年级档，**144** 个内置单元。

### 与教材的对应关系

- **目录**：参考沪教牛津版（六三制）公开课本目录（教习网、好多电子课本等）。
- **一至二年级、四至五年级**：经典版，**12 单元/册**。
- **三年级**：2024 新教材，**8 单元/册**。
- **五年级下册**：官方目录 Module 2 无 Unit 6，共 11 单元。

带读句为围绕单元主题的**原创短句**（每行 ≤10 词），**非教材原文**，便于跟读且避免版权问题。

### 牛津阅读树（`ort_dialogue`）

- **12 课**家庭情景：起床、找 Floppy、公园、下雨、商店、小钥匙、丢玩具、睡前、上学、野餐等。
- 角色：**Biff、Chip、Kipper**、Mum、Dad、**Floppy**（与书里一致）；句式为原创短句，**不摘抄** ORT 教材原文。
- **带读入口**：首页 → 年级选 **「牛津阅读树」**（拓展）→ 选第几课 → 预热 → **开始带读**。

## 重生成课文 JSON

编辑生成脚本后执行：

```bash
cd english-buddy/backend
python3 teaching/build_lessons_v5.py
```

会覆盖 `lessons.json`。重启后端后 `curriculum_version` 变更触发重灌。

生成脚本：`backend/teaching/build_lessons_v5.py`  
年级元数据：`lessons.json` 内 `grades` 数组 + `teaching/grades.py` 读取。

## 自定义课文

- 存 SQLite，`grade_id = custom`，`owner_user_id` 绑定登录用户。
- 任意年级下选课列表都会出现该用户的自定义项（须登录）。
- 须按**当前老师 + 语速**手动预热。
- 内置课文：`BUILTIN_PREWARM=1` 后台**并发**预热（`BUILTIN_PREWARM_CONCURRENCY`，默认 4）；首页**只展示已预热**的课文。

手动跑完全部预热：

```bash
cd english-buddy && python3 scripts/prewarm_builtin.py
```

进度 API：`GET /api/lessons/prewarm/builtin?program=elsa_snow&tts_speed=1.0`

## 老师与课文

艾莎 / 奥特曼只影响人设与 TTS 音色；**课文与年级绑定**，两位老师共用同一套内置库。

## 教学法

带读时 LLM 注入 `backend/teaching/playbook_age4_read_along.md`（4 岁跟读 SOP）。  
公开资源链接：`GET /api/teaching/references`。

旧版「艾莎场馆导览」示例说明见 `backend/teaching/elsa_curriculum.md`（历史参考，非当前主课文库）。
