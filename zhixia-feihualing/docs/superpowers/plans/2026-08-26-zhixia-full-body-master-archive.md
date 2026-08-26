# 栀夏全身比例长裙母板归档 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将用户确认的栀夏长裙三视图安全归档为全身比例制作母板，并同步角色服装单一事实源与资产清单。

**Architecture:** 原始 PNG 以版本化文件名保存到角色资产目录，不做重采样或二次压缩。`docs/character-bible.md` 只更新固定服装，不改变身份、发冠和表演设定；`assets/inventory.csv` 记录资产用途、状态和参考优先级。身份主卡继续负责脸、发型和发冠，全身比例卡只负责身体比例、长裙结构和鞋履。

**Tech Stack:** PNG 文件资产、Markdown 角色母版、CSV 资产清单、macOS `sips`、`shasum`、Python 标准库 `csv`、Git。

## Global Constraints

- 用户确认的源图为 `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png`。
- 归档目标为 `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`。
- 不重采样、不裁切、不调色、不覆盖 `栀夏角色卡电影半写实-v01.png`。
- 身份主卡负责脸型、五官、年龄、发型和发冠；全身比例卡只负责身体比例、盛唐轻薄长裙、薄纱结构和鞋履。
- 短裙、侧开短裙及“内短外长”薄纱方案全部作废。
- 角色保持“电影级半写实东方幻想角色＋高度写实衣料、材质与光线”，不得改成现实真人、动漫或游戏 CG。
- 只提交本计划列出的文件，不带入工作区其他修改。

---

### Task 1: 原样归档长裙三视图 PNG

**Files:**
- Create: `zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png`
- Source: `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png`

**Interfaces:**
- Consumes: 用户确认的原始 PNG。
- Produces: 后续角色比例质检和分镜生成可引用的版本化全身比例母板。

- [ ] **Step 1: 验证源图存在且为可读取的 PNG**

Run:

```bash
test -f /var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png
sips -g format -g pixelWidth -g pixelHeight /var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png
```

Expected: 文件存在，`format: png`，宽高均为正整数。

- [ ] **Step 2: 确认目标文件尚未存在**

Run:

```bash
test ! -e zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
```

Expected: 退出码为 0；若目标已存在，停止并比较两份文件，不直接覆盖。

- [ ] **Step 3: 原样复制图片**

Run:

```bash
cp /var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
```

- [ ] **Step 4: 验证源文件与归档文件逐字节一致**

Run:

```bash
cmp /var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
shasum -a 256 /var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-a1f45c98-b88a-4d2d-9921-86a257fe6b0c.png zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
```

Expected: `cmp` 退出码为 0，两行 SHA-256 值相同。

- [ ] **Step 5: 提交图片资产**

```bash
git add zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
git commit -m "资产：归档栀夏长裙全身比例卡"
```

### Task 2: 更新栀夏固定服装母版

**Files:**
- Modify: `zhixia-feihualing/docs/character-bible.md`

**Interfaces:**
- Consumes: 已确认的长裙设计规格和归档图片。
- Produces: 后续提示词使用的角色固定服装单一事实源。

- [ ] **Step 1: 记录修改前的旧服装条目**

Run:

```bash
sed -n '12,18p' zhixia-feihualing/docs/character-bible.md
```

Expected: 当前仍包含“低饱和浅青色汉风交领常服”等旧条目，证明文档需要更新。

- [ ] **Step 2: 将“固定服装”替换为已确认长裙结构**

Use `apply_patch` to replace the four bullets under `### 固定服装` with:

```markdown
- 月白偏浅青色的盛唐式丝绢抹胸，领缘端正、覆盖充分
- 低饱和浅青色盛唐高腰长裙，裙摆自然垂至脚踝附近并露出鞋履
- 月白浅青色半透明薄罗纱大袖衫，衣襟敞开并连续覆盖肩背
- 极淡浅粉色细腰带、少量白色花纹与哑光暖金细线
- 月白偏浅青色盛唐平底云头履
- 禁止短裙、高开衩、侧开露腿、现代内衣结构和拖地遮鞋
```

- [ ] **Step 3: 验证新旧规则不存在冲突**

Run:

```bash
sed -n '1,32p' zhixia-feihualing/docs/character-bible.md
rg -n '交领常服|短裙|高开衩|盛唐高腰长裙|平底云头履' zhixia-feihualing/docs/character-bible.md
```

Expected: 固定服装只保留长裙方案；“短裙”和“高开衩”仅出现在禁止项中；身份与发冠段落未变化。

- [ ] **Step 4: 提交角色母版更新**

```bash
git add zhixia-feihualing/docs/character-bible.md
git commit -m "文档：固定栀夏盛唐长裙服装"
```

### Task 3: 登记全身比例母板并完成交叉验证

**Files:**
- Modify: `zhixia-feihualing/assets/inventory.csv`

**Interfaces:**
- Consumes: Task 1 的归档路径与 Task 2 的角色服装规则。
- Produces: 唯一资产 ID `zhixia-full-body-cinematic-semi-real-v01` 和可查询的 approved 资产记录。

- [ ] **Step 1: 验证资产 ID 尚未登记**

Run:

```bash
! rg -n '^zhixia-full-body-cinematic-semi-real-v01,' zhixia-feihualing/assets/inventory.csv
```

Expected: 退出码为 0，表示不存在重复 ID。

- [ ] **Step 2: 在 CSV 末尾添加唯一记录**

Append exactly one CSV row:

```csv
zhixia-full-body-cinematic-semi-real-v01,character,栀夏,full-body-master,assets/characters/栀夏全身比例卡电影半写实-v01.png,approved,ChatGPT generated image,original AI-assisted asset,长裙正面右侧面背面三视图；盛唐轻薄夏装；负责身体比例服装结构和鞋履；脸型发型发冠仍以身份主卡为准
```

- [ ] **Step 3: 使用 Python 标准库验证 CSV 和文件引用**

Run:

```bash
python3 -c 'import csv,pathlib; p=pathlib.Path("zhixia-feihualing/assets/inventory.csv"); rows=list(csv.DictReader(p.open(encoding="utf-8"))); hit=[r for r in rows if r["asset_id"]=="zhixia-full-body-cinematic-semi-real-v01"]; assert len(hit)==1, len(hit); r=hit[0]; assert r["status"]=="approved"; assert pathlib.Path("zhixia-feihualing", r["path_or_url"]).is_file(); print(r["path_or_url"])'
```

Expected: 打印 `assets/characters/栀夏全身比例卡电影半写实-v01.png`，退出码为 0。

- [ ] **Step 4: 检查三份交付物和提交范围**

Run:

```bash
git status --short -- zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png zhixia-feihualing/docs/character-bible.md zhixia-feihualing/assets/inventory.csv
git diff --check -- zhixia-feihualing/docs/character-bible.md zhixia-feihualing/assets/inventory.csv
```

Expected: 仅 `assets/inventory.csv` 尚未提交；`git diff --check` 无输出。

- [ ] **Step 5: 提交资产清单**

```bash
git add zhixia-feihualing/assets/inventory.csv
git commit -m "资产：登记栀夏全身比例母板"
```

- [ ] **Step 6: 最终验证**

Run:

```bash
sips -g format -g pixelWidth -g pixelHeight zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png
rg -n '^zhixia-full-body-cinematic-semi-real-v01,' zhixia-feihualing/assets/inventory.csv
git status --short -- zhixia-feihualing/assets/characters/栀夏全身比例卡电影半写实-v01.png zhixia-feihualing/docs/character-bible.md zhixia-feihualing/assets/inventory.csv
```

Expected: 图片为 PNG 且尺寸有效；资产 ID 恰好出现一次；三个交付文件没有未提交修改。
