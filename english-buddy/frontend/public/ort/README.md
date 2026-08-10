# ORT 页图

按页带读插图放在本目录，路径与 `catalog.json` 中 `pages[].image` 一致，例如：

```
ort/ort_who_is_it/p01.jpg
ort/ort_who_is_it/p02.jpg
```

缺图时专题页**不展示**该读本；配图通话中缺页会显示 `placeholder.svg`。

**同页多句**：`books.json` 里同一 `pages[]` 项可含多个 `lines`（与书上排版一致）；带读时「本页句子」全部展示，老师按序念完。详见 `docs/ORT_READ_ALONG.md`。

## 从橙果 PDF 提取页图

`Documents/级别 (3)【橙果玩英语】/` 等扫描 PDF 每页一张插图（需旋转 -90°）。故事页从 PDF 第 3 页起（跳过封面与家长导读）。

```bash
cd english-buddy
.venv/bin/pip install pymupdf pillow   # 首次

.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --pdf "$HOME/Documents/级别 (3)【橙果玩英语】/3-01 The Duck Race.pdf" \
  --book ort_the_duck_race
```

页数默认读 `catalog.json` 的 `page_count`；输出到 `ort/{book_id}/p01.jpg`。

**批量 Level 2 / 3**（图与课文分离；课文在 `books.json`，勿 OCR PDF）：

```bash
# Level 2 — 见 .cursor/skills/ort-chengguo-import/SKILL.md
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level 2 \
  --batch-dir "$HOME/Documents/Oxfordreadingtree/级别 (2)【橙果玩英语】"

# Level 3（兼容旧参数）
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level3 "$HOME/Documents/Oxfordreadingtree/级别 (3)【橙果玩英语】"
```

专题页封面块用 PDF 第 1 页 `cover.jpg`（故事页仍从第 3 页起）：

```bash
.venv/bin/python scripts/extract_ort_pdf_pages.py \
  --batch-level3-covers "$HOME/Documents/级别 (3)【橙果玩英语】"
```

个别 PDF 故事页少于 catalog（如 Sniff 仅 18 页）需手动 `--pages 18` 并复制末页补齐 `p19`/`p20`。

**一页多句**（句数多于插图页）：编辑 `books.json` 的 `pages[]` 或 `scripts/sync_ort_page_groups.py`，见 `.cursor/skills/ort-chengguo-import/SKILL.md`。

抓完后 `./scripts/restart.sh --build`，PWA 点「刷新」。
