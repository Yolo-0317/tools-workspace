# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one 9:16 full-body main image of Ayan’s adult heavenly-palace human form for later dual-female Latin dance videos.

**Architecture:** Use the approved Ayan masterboard as the identity-and-markings reference and the approved Zhixia heavenly-palace image only as a scene, material-quality, and costume-polish reference. Generate one project-bound working image with the built-in image tool, inspect all structural invariants, and preserve it non-destructively for user review before any character-card work.

**Tech Stack:** Codex built-in image generation, local image inspection, PNG metadata verification.

## Global Constraints

- Ayan is an adult woman around age 18 and 162cm tall; no childlike or chibi proportions.
- Preserve brush-tip cat ears, exactly one open S-shaped ink tail, warm amber eyes, central cinnabar forehead mark, paper-white/ink/gold motifs.
- Costume uses an ivory shallow sweetheart strapless bodice and exactly two narrow upper-arm ink-tip ribbons; no deep V, exaggerated cleavage, or duplicated Zhixia costume.
- Full body, both hands, both shoes, both ears, and the full tail must be visible in a 9:16 composition.
- No text, card layout, border, watermark, other character, animal, prop, weapon, extra limb, extra ear, or extra tail.

---

### Task 1: Generate and inspect the working main image

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg`
- Reference: `zhixia-feihualing/assets/characters/归档/栀夏天宫探戈形象-v01-正式版.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v01.png`

**Interfaces:**
- Consumes: two local reference images with explicitly separated roles.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect both references**

Open the Ayan masterboard and confirm the brush-tip ears, single ink tail, amber eyes, cinnabar mark, paper-white body, pale ink texture, and warm-gold spiral cloud motif. Open the Zhixia heavenly image and use only its warm-gold heavenly-palace atmosphere, realistic CG finish, ivory fabric quality, and adult Latin-dance styling; do not copy Zhixia’s face, crown, body proportions, exact bodice outline, or wide white ribbons.

- [ ] **Step 2: Generate one main-image candidate**

Use the built-in image generator with both references and this production prompt:

```text
Use case: identity-preserve
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project
Input images: Image 1 is the authoritative identity and markings reference for Ayan; Image 2 is only a reference for heavenly-palace atmosphere, photoreal CG finish, ivory fabric quality, and adult Latin-dance styling. Never copy Image 2’s face, crown, body proportions, exact bodice, or wide ribbons.

Primary request: Transform Ayan from Image 1 into her temporary adult human form used only in the heavenly-palace series. She is an East Asian adult woman around age 18, 162cm tall, petite and light with natural adult proportions, narrow shoulders, and a distinct face that is not Zhixia. Preserve Ayan’s calm, bright, agile personality.

Identity invariants: exactly two upward-outward brush-tip cat ears integrated naturally with the hair; exactly one open S-shaped ink tail growing clearly from the tailbone, never forked or detached; bright warm amber eyes; one small fixed cinnabar-red mark centered on the forehead; paper-white, pale ink dry-brush, and pale warm-gold spiral-cloud visual language. No ordinary round cosplay ears, no human-ear emphasis, no second tail.

Hair and face: adult East Asian face, lively but not childish, natural slight smile, deep ink-black long hair in a light half-up style, only a tiny pale-gold cloud-pattern hairpin and one small cinnabar accent. Do not copy Zhixia’s face or heavenly crown.

Costume: elegant ivory-white adult Latin dance costume. A secure shallow sweetheart strapless bodice fully covers and supports the chest, with restrained pale-ink dry-brush edging, no deep V and no exaggerated cleavage. An asymmetric fitted dance skirt opens from the waist, longest point at mid-calf and shorter side still covering the upper thigh. One restrained pale warm-gold spiral-cloud motif crosses the waist and skirt. Exactly two narrow ink-tip cloud ribbons, one fixed to the back-outer side of each upper arm; translucent paper-white chiffon gradually fades to pale ink at the tips, with one fine pale-gold edge, ending below the knees without touching the floor. The ribbons are much narrower and shorter than Zhixia’s wide pure-white drapes. Ivory 4.5cm stable Latin heels.

Pose and composition: single character, full body in a vertical 9:16 frame; front view turned slightly three-quarter, natural weight on one foot and the other toe lightly touching as a cha-cha preparation pose; one hand naturally open and the other held near but outside the waist. Show the entire head, both brush-tip ears, both hands, both shoes, and the full single tail. Keep the two ribbons visually separated from arms, torso, skirt, legs, and tail.

Scene and style: warm-gold dawn heavenly palace, luminous cloud sea and pale jade steps, simple depth without distracting figures. Cinematic high-realism CG, natural adult skin, realistic silk and chiffon, refined Chinese fantasy atmosphere, clear anatomy, character is the only subject.

Avoid: child, minor, chibi, doll face, sexualized juvenile, exaggerated bust, deep neckline, Zhixia face, Zhixia crown, copied Zhixia dress, wide pure-white arm drapes, extra person, animal, text, character-sheet layout, watermark, border, weapon, prop, collar, bell, paws, cat nose, whiskers, body fur, extra fingers, fused hands, extra limbs, missing limbs, extra ears, round ears, extra tail, split tail, looped tail, detached tail, ribbons fused into the body or legs.
```

- [ ] **Step 3: Persist the generated candidate in the workspace**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v01.png` without overwriting any existing sibling version.

- [ ] **Step 4: Verify image metadata and perform visual QA**

Verify the saved file is a readable portrait PNG. Inspect it at full resolution and confirm the adult proportions, distinct face, exactly two brush-tip ears, one connected S-shaped tail, amber eyes, cinnabar mark, shallow sweetheart bodice, exactly two narrow ink-tip ribbons, complete hands and shoes, and absence of text or other figures. If a structural invariant fails, run one targeted image-edit iteration changing only the failed item and re-inspect.

- [ ] **Step 5: Commit the approved working candidate only after visual inspection**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v01.png
git commit -m "生成阿砚天宫限定人形主图"
```
