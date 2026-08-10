# Oxford Reading Tree（Oxford Owl 免费库）

真源：`books.json` — 按 Level 分年级灌入 `lessons.json`（`ort_l1` / `ort_l1plus` / `ort_l3` / `ort_l4`）。

听读/带读运行时约定见 [`docs/ORT_READ_ALONG.md`](../../docs/ORT_READ_ALONG.md)。

## 来源

- [Oxford Owl 免费电子书库 · Oxford Reading Tree](https://www.oxfordowl.co.uk/for-home/find-a-book/library-page/?series=Oxford+Reading+Tree)
- 注册/登录后可在线阅读完整插图版；本仓库收录的是带读用**英文原句**（与纸质 Stage 1 读本一致）。

## 更新课文

1. 编辑 `books.json`（增删 `books[]`、改 `lines` 或 **`pages[].lines` 同页多句**）
   - L3/L4 分页对照 `ort_l3_page_groups.json` / `ort_l4_page_groups.json`（`scripts/apply_ort_pdf_page_groups.py --level 4`）
   - 页图路径 `ort_{book_id}/pNN.jpg` 与 `pages[]` 顺序一致
2. 重新生成：

```bash
cd english-buddy/backend && python3 teaching/build_lessons_v5.py
```

3. 重启后端；`version` 变更后会重灌 SQLite 并清理改动课的 TTS 预热。

## 页图：橙果 PDF

本地 `Documents/级别 (N)【橙果玩英语】/`（图与课文分离，课文在 `books.json`）：

```bash
cd english-buddy
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --pdf "$HOME/Documents/级别 (3)【橙果玩英语】/3-01 The Duck Race.pdf" \
  --book ort_the_duck_race
```

完整流程见 `.cursor/skills/ort-chengguo-import/SKILL.md` 与 `frontend/public/ort/README.md`。

## 文本校验

```bash
cd english-buddy
python3 scripts/sync_oxford_owl_ort.py
```

默认以 `books.json` 手维真源为准。
