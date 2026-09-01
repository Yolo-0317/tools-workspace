# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one 9:16 Ayan main-image candidate whose only change from the approved v04b composition is a pair of Zhixia-matching closed-toe high heels with Ayan’s ivory, pale-gold, and smoke-ink color language.

**Architecture:** Use v04b as the sole edit target and the confirmed Zhixia Heavenly Palace character card only as a footwear-shape reference. Perform one precise two-shoe edit, lock every non-footwear invariant, save the result as v04c without overwriting earlier candidates, and inspect shoe silhouette, color treatment, anatomy, and identity preservation before user review.

**Tech Stack:** Codex built-in image editing, local image inspection, PNG metadata verification.

## Global Constraints

- Preserve v04b’s exact Ayan face, short layered hair, brush-tip ears, cinnabar mark, body proportions, pose, hands, single ink tail, costume, broad ink-tip ribbons, heavenly-palace background, lighting, and framing.
- Both shoes use Zhixia’s moon-white closed-toe tango-shoe silhouette, stable enclosed heel cups, simple crossed instep straps, and approximately 5.5cm flared heels.
- Ayan’s version uses matte ivory satin, pale warm-gold spiral-cloud patterns at the toe and sides, a restrained smoke-ink gradient from heel toward the sides, and smoke-ink heels edged by one fine pale-gold line.
- Do not copy Zhixia’s face, body, hair, crown, costume, pose, card layout, or text; Image 2 controls footwear silhouette only.
- No exposed toes, flat shoes, cloud-toe shoes, concealed low curved heels, stilettos, platforms, metal buckles, patent leather, all-black uppers, mismatched shoes, floating feet, or distorted ankles.
- Save non-destructively as `assets/characters/work/阿砚天宫限定人形小女伴主图-v04c-栀夏同款高跟鞋.png`.

---

### Task 1: Edit and inspect Ayan’s footwear

**Files:**
- Edit target: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04b-云头舞履.png`
- Footwear-shape reference: `/var/folders/k9/byvrwvls2y384yw4hq3gpqkm0000gn/T/codex-clipboard-2189f009-531a-4199-8bac-abb4ea51cfb1.jpg`
- Supporting written reference: `zhixia-feihualing/assets/characters/栀夏天宫探戈角色母板-v01-Seedance固定说明.md`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04c-栀夏同款高跟鞋.png`

**Interfaces:**
- Consumes: one Ayan edit target, one Zhixia card restricted to shoe silhouette, and the confirmed design spec.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect the edit target and footwear reference**

Open v04b and confirm the exact non-footwear invariants to preserve. Open the Zhixia card and inspect only the front and side shoe modules: closed moon-white toe, pale-gold edging, enclosed heel cup, simple crossed instep straps, and approximately 5.5cm pale-gold flared heel. Do not use any Zhixia face, body, hair, crown, clothing, or layout feature as an edit reference.

- [ ] **Step 2: Perform one precise footwear edit**

Use the built-in image editor with v04b as Image 1 and the Zhixia card as Image 2:

```text
Use case: precise-object-edit
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project

Input-image roles:
Image 1 is the edit target and the sole authority for Ayan’s identity, face, body, hair, ears, forehead mark, tail, pose, hands, costume, ribbons, scene, lighting, framing, and every non-footwear detail.
Image 2 is only a footwear-shape reference. Read only Zhixia’s moon-white closed-toe tango shoes: rounded closed toe, elegant low-cut instep opening, stable enclosed heel cup, simple crossed instep straps, and approximately 5.5cm flared heel. Ignore and never copy Image 2’s face, body, hair, crown, clothing, card layout, text, or background.

Primary request: change only both shoes and their immediate floor-contact shadows in Image 1. Replace the current shoes with the same elegant closed-toe high-heel silhouette and the same heel height as Zhixia’s shoes in Image 2. Preserve realistic foot anatomy, ankle alignment, grounded outsoles, and the original leg pose.

Ayan color treatment: matte ivory woven-satin upper; restrained pale warm-gold spiral-cloud patterns across the toe box and outer side; a controlled smoke-ink gradient beginning at the enclosed heel cup and fading forward along the outer side; smoke-ink flared heel with one fine pale-gold edge. Keep most of each upper ivory so the shoe remains light and elegant. Both shoes must match exactly in silhouette, pattern language, heel height, and color placement.

Hard invariants: preserve Image 1’s exact Ayan face and expression, short layered hair, exactly two brush-tip ears, cinnabar forehead mark, body proportions, pose, both hands, exactly one connected ink tail, shallow sweetheart bodice, diagonal smoke-ink skirt, exactly two broad ink-tip ribbons, heavenly-palace architecture, cloud sea, lighting, composition, and 9:16 framing. Do not change any garment edge or leg anatomy.

Avoid: exposed toes, sandals, flat shoes, cloud-toe shoes, concealed low curved heels, stilettos, platforms, metal buckles, patent leather, all-black shoes, complicated ankle wraps, mismatched left and right shoes, floating soles, warped feet, twisted ankles, changed pose, changed identity, Zhixia face, Zhixia costume, extra limbs, text, card layout, watermark.
```

- [ ] **Step 3: Save non-destructively and verify metadata**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04c-栀夏同款高跟鞋.png` without overwriting v04 or v04b. Verify that it is a readable portrait PNG and record its pixel dimensions and SHA-256 hash.

- [ ] **Step 4: Perform visual QA**

Inspect v04c at full resolution. Confirm both shoes have the same Zhixia-style closed-toe silhouette and approximately 5.5cm flared heel; ivory uppers remain dominant; pale-gold cloud patterns, side smoke-ink gradients, and smoke-ink heels are visible; both feet contact the floor naturally. Compare v04c with v04b and reject it if any non-footwear feature drifts, if the shoes remain cloud-toe or low-heeled, or if the pair differs in shape or color.

- [ ] **Step 5: Commit only after user approval**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04c-栀夏同款高跟鞋.png
git commit -m "生成阿砚天宫同款高跟鞋主图"
```
