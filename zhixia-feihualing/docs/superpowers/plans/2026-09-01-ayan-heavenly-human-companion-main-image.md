# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one 9:16 Ayan main-image candidate whose only change from v04d is a cuter, more innocent adult face without the previous seductive or fox-like impression.

**Architecture:** Use v04d as the only edit input and perform one face-and-expression edit limited to the facial region. Preserve hair, ears, forehead mark, body, costume, ribbons, ink-pattern shoes, scene, and framing; save the result as v05 without overwriting earlier candidates, then inspect adult age, cuteness, absence of seductive cues, and non-face identity preservation before user review.

**Tech Stack:** Codex built-in image editing, local image inspection, PNG metadata verification.

## Global Constraints

- Preserve v04d’s exact shoulder-length layered hair, two brush-tip ears, cinnabar forehead mark, body proportions, pose, hands, single ink tail, costume, broad ink-tip ribbons, white-and-ink high heels, heavenly-palace background, lighting, and framing.
- Face is an adult East Asian woman around age 18 with a short round oval shape, fuller soft apple cheeks, a short rounded chin, slightly wider-set warm-amber almond eyes that are slightly larger and rounder while remaining photorealistic, near-horizontal outer eye corners, short flat soft brows, a small natural nose, and naturally full lips with reduced mature cupid’s bow and reduced upturned corners.
- Expression is a clear direct gaze and a natural closed-mouth gentle smile: bright, candid, innocent, friendly, and adult.
- No pointed chin, narrow fox-like face, strongly upturned seductive eyes, narrowed eyes, raised brows, mature red lips, alluring stare, cat-demon expression, exaggerated anime eyes, baby proportions, or doll face.
- Save non-destructively as `assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`.

---

### Task 1: Edit and inspect Ayan’s face

**Files:**
- Edit target: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04d-白底墨纹高跟鞋.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png`

**Interfaces:**
- Consumes: one Ayan v04d edit target and the confirmed design spec.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect the edit target**

Open v04d and confirm the exact hairline, layered hair, brush-tip ears, forehead mark, body, clothing, ribbons, tail, shoes, pose, scene, lighting, and framing to preserve. Identify the facial cues to remove: strongly upturned outer eye corners, a narrow mature gaze, insufficient cheek fullness, and a mature slightly alluring mouth expression.

- [ ] **Step 2: Perform one precise face edit**

Use the built-in image editor with v04d as the only image input:

```text
Use case: precise-object-edit
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project

Input image: Image 1 is the edit target and the sole authority for every visible feature.

Primary request: change only Ayan’s facial geometry and expression inside the face region. Make her look cuter, more candid, and more innocent while remaining clearly an adult East Asian woman around age 18 and retaining a realistic live-action face.

Face design: use a short round oval face with fuller soft apple cheeks and a short rounded chin, preserving natural adult bone structure. Keep warm-amber almond eyes slightly wide-set; make them slightly larger and rounder than Image 1 while preserving real human proportions. Reduce the upward slant clearly so both outer eye corners are almost horizontal. Use short flat soft brows with no sharp arch. Keep a small natural nose. Preserve naturally full lips but soften the mature cupid’s bow and reduce the upward pull at the mouth corners. Expression is a clear direct gaze and a subtle natural closed-mouth smile: bright, candid, innocent, friendly, and not childish.

Hard invariants: preserve Image 1’s exact hairline, shoulder-length layered hairstyle, individual flyaway strands, exactly two brush-tip ears, central cinnabar forehead mark and its position, skin tone and natural matte texture, body proportions, pose, both hands, exactly one connected ink tail, shallow sweetheart bodice, diagonal smoke-ink skirt, exactly two broad ink-tip ribbons, white-and-ink closed-toe high heels, heavenly-palace architecture, cloud sea, lighting, composition, and 9:16 framing. Do not change anything below the jaw or outside the facial region.

Avoid: pointed chin, narrow elongated fox-like face, strongly upturned seductive eyes, narrowed eyes, raised or sharply arched brows, mature red lips, pronounced seductive cupid’s bow, alluring stare, cat-demon expression, heavy eyeliner, exaggerated anime eyes, baby face, child, minor, infant proportions, doll face, excessive cheek puffiness, resemblance to Zhixia, changed forehead mark, changed ears, changed hair, changed costume, changed shoes, changed pose, extra limbs, text, card layout, watermark.
```

- [ ] **Step 3: Save non-destructively and verify metadata**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png` without overwriting v04d. Verify that it is a readable portrait PNG and record its pixel dimensions and SHA-256 hash.

- [ ] **Step 4: Perform visual QA**

Inspect v05 at full resolution. Confirm the face remains adult and photorealistic while showing a shorter rounder shape, fuller soft cheeks, shorter rounded chin, slightly larger and rounder real-human amber almond eyes, near-horizontal outer corners, short flat soft brows, and a candid closed-mouth gentle smile. Compare v05 with v04d and reject it if seductive or fox-like cues remain, if the face becomes childlike or doll-like, if it resembles Zhixia, or if any non-face feature drifts.

- [ ] **Step 5: Commit only after user approval**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v05-天真圆脸.png
git commit -m "生成阿砚天真圆脸主图"
```
