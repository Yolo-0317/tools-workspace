# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce one 9:16 Ayan main-image candidate whose only change from v04c is replacing every gold footwear decoration with ink while preserving the approved Zhixia-matching high-heel silhouette.

**Architecture:** Use v04c as the only edit input because its shoe silhouette is already correct; do not provide the Zhixia card again. Perform one precise footwear recolor, lock all shapes and every non-footwear invariant, save the result as v04d without overwriting earlier candidates, and inspect the absence of gold, ink visibility, anatomy, and identity preservation before user review.

**Tech Stack:** Codex built-in image editing, local image inspection, PNG metadata verification.

## Global Constraints

- Preserve v04c’s exact Ayan face, short layered hair, brush-tip ears, cinnabar mark, body proportions, pose, hands, single ink tail, costume, broad ink-tip ribbons, heavenly-palace background, lighting, framing, and shoe shape.
- Both shoes use Zhixia’s moon-white closed-toe tango-shoe silhouette, stable enclosed heel cups, simple crossed instep straps, and approximately 5.5cm flared heels.
- Ayan’s version uses matte ivory satin with clearly visible smoke-ink to deep-ink spiral-cloud patterns, shoe-opening edging, structural lines, crossed instep straps, and deep-ink flared heels; there is no gold anywhere on either shoe.
- No exposed toes, flat shoes, cloud-toe shoes, concealed low curved heels, stilettos, platforms, metal buckles, patent leather, all-black uppers, mismatched shoes, floating feet, or distorted ankles.
- Save non-destructively as `assets/characters/work/阿砚天宫限定人形小女伴主图-v04d-白底墨纹高跟鞋.png`.

---

### Task 1: Edit and inspect Ayan’s footwear

**Files:**
- Edit target: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04c-栀夏同款高跟鞋.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04d-白底墨纹高跟鞋.png`

**Interfaces:**
- Consumes: one Ayan v04c edit target and the confirmed design spec.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect the edit target**

Open v04c and confirm the exact non-footwear invariants and both shoe silhouettes to preserve. Identify every gold area on each shoe: toe and side cloud motifs, shoe-opening edging, structural lines, crossed instep straps, and any gold visible on the flared heels.

- [ ] **Step 2: Perform one precise footwear edit**

Use the built-in image editor with v04c as the only image input:

```text
Use case: precise-object-edit
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project

Input image: Image 1 is the edit target and the sole authority for every visible feature.

Primary request: change only the colors of both shoes. Preserve their exact closed-toe shape, low-cut instep opening, enclosed heel cup, crossed instep straps, approximately 5.5cm flared heels, foot anatomy, ankle alignment, grounded outsoles, and original leg pose.

Footwear recolor: keep the main woven-satin uppers matte ivory. Replace every gold element on both shoes with clearly visible ink: change all gold spiral-cloud motifs on the toe boxes and outer sides to smoke-ink and deep-ink brushwork; change every gold shoe-opening edge and structural line to dark ink; change both crossed instep straps from gold or ivory-gold to smoke ink; change both flared heels to deep ink. No gold may remain anywhere on either shoe. Keep the pair identical and keep the ivory ground dominant so they do not become solid black shoes.

Hard invariants: preserve Image 1’s exact Ayan face and expression, short layered hair, exactly two brush-tip ears, cinnabar forehead mark, body proportions, pose, both hands, exactly one connected ink tail, shallow sweetheart bodice, diagonal smoke-ink skirt, exactly two broad ink-tip ribbons, heavenly-palace architecture, cloud sea, lighting, composition, and 9:16 framing. Do not change any garment edge or leg anatomy.

Avoid: any gold on either shoe, changed shoe silhouette, exposed toes, sandals, flat shoes, cloud-toe shoes, concealed low curved heels, stilettos, platforms, metal buckles, patent leather, all-black shoes, complicated ankle wraps, mismatched left and right shoes, floating soles, warped feet, twisted ankles, changed pose, changed identity, changed clothing, extra limbs, text, card layout, watermark.
```

- [ ] **Step 3: Save non-destructively and verify metadata**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04d-白底墨纹高跟鞋.png` without overwriting v04c. Verify that it is a readable portrait PNG and record its pixel dimensions and SHA-256 hash.

- [ ] **Step 4: Perform visual QA**

Inspect v04d at full resolution. Confirm both shoes retain the exact v04c closed-toe silhouette and approximately 5.5cm flared heel; ivory uppers remain dominant; cloud motifs, edging, structural lines, crossed straps, and heels are visibly ink-colored; no gold remains on either shoe; both feet contact the floor naturally. Compare v04d with v04c and reject it if any non-footwear feature or shoe shape drifts, if gold remains, or if the pair differs in shape or color.

- [ ] **Step 5: Commit only after user approval**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04d-白底墨纹高跟鞋.png
git commit -m "生成阿砚白底墨纹高跟鞋主图"
```
