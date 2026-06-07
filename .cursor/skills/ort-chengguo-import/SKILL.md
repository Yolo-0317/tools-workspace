---
name: ort-chengguo-import
description: >-
  橙果玩英语 ORT PDF 页图导入与课文维护。用户提到橙果 PDF、Oxfordreadingtree、
  Level 2/3 批量插图、ORT 专题上新时使用。图与课文分离，禁止 PDF OCR 取课文。
---

# ORT 橙果 PDF 导入

## 原则（必读）

| 内容 | 真源 | 禁止 |
|------|------|------|
| **页图** `frontend/public/ort/{book_id}/pNN.jpg` | 橙果 PDF，`extract_ort_pdf_pages.py` | — |
| **课文** `books.json` → `lines[]` 或 `pages[].lines` | 爱贝指导 / Oxford Owl 人工录入 / `chengguo_level2_manual.json` | **勿 OCR PDF**、勿 easyocr |

PDF 结构：p1 封面、p2 家长导读、p3… 故事页（默认 `--story-start 3`）。

## 一页多句（图与句对不上）

**现象**：实体书一页两句，但带读按「一句一页一图」推进，插图错位。

**模型**：`books.json` 支持 `pages[]`——同一 `image` 下可挂多句 `lines`；带读仍按句推进，**翻图**仅在进入下一 `pages[]` 项时切换（前端 `ortLinePageIndex` 已支持）。

```bash
# 预览：每连续 2 句合并为一插图页
.venv/bin/python scripts/sync_ort_page_groups.py --book ort_the_go_kart --lines-per-page 2 --dry-run

# 写入 books.json（均匀分到 N 张图，适合已知 PDF 故事页数）
.venv/bin/python scripts/sync_ort_page_groups.py --book ort_the_toys_party --image-pages 8

# 应用后必做
cd backend && python3 -c "from teaching.ort_oxford_owl.catalog import write_catalog; write_catalog(13)"
python3 teaching/build_lessons_v5.py
.venv/bin/python scripts/extract_ort_pdf_pages.py --batch-level 2 --batch-dir "..."
./scripts/restart.sh --build
```

混合排版（有的页 1 句、有的 2 句）：直接编辑 `books.json` 的 `pages[]`，勿盲目整级 `--lines-per-page 2`。

L3 已校对示例：`ort_a_cat_in_the_tree`（16 插图页 / 17 句，首页两句）— 参考 `ort_l3_page_groups.json`。

## 路径约定

- PDF 目录示例：`~/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】/`
- 映射表：`english-buddy/backend/teaching/ort_oxford_owl/chengguo_maps.py`
- 爱贝 aid 表：`IBEI_LEVEL2_AIDS`（≠ 橙果 2-XX 序号，已人工校对）

## Level 2 完整流程

```bash
cd english-buddy
.venv/bin/pip install pymupdf pillow   # 首次

# 1. 拉爱贝课文（可选，输出 JSON）
.venv/bin/python scripts/fetch_chengguo_ibei_lines.py

# 2. 合并进 books.json（爱贝 + manual JSON）
.venv/bin/python scripts/merge_ort_chengguo_books.py

# 3. 批量页图 + 封面
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level 2 \
  --batch-dir "$HOME/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】"
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level2-covers "$HOME/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】"

# 4. 重建 catalog + lessons
cd backend && python3 -c "from teaching.ort_oxford_owl.catalog import write_catalog; write_catalog(13)"
python3 teaching/build_lessons_v5.py

# 5. 部署
cd .. && ./scripts/restart.sh --build
```

缺课文：编辑 `chengguo_level2_manual.json` 或 `books.json`，再跑 merge（`--dry-run` 可预览）。

## Level 3（已有）

```bash
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level 3 \
  --batch-dir "$HOME/Documents/Oxfordreadingtree/级别 (3)【橙果玩英语】"
```

## 单本调试

```bash
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --pdf "$HOME/Documents/.../2-01 The Toy's Party.pdf" \
  --book ort_the_toys_party
```

## 前端

- Level Tab：`frontend/src/config/ort.ts`（`ort_l2` / `ORT_LEVEL_TABS`）
- 专题只显示 `images_ready` 读本

## 勿做

- 不要 `pip install easyocr` 或从 PDF 扫课文
- 不要把 `frontend/public/ort/*.jpg` 当课文真源
- 爱贝 aid 不要按 2-01→31049 递增假设，以 `chengguo_maps.py` 为准
