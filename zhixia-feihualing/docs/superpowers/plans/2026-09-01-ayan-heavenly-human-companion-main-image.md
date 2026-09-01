# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one 9:16 full-body main image of Ayan’s adult heavenly-palace human form for later dual-female Latin dance videos.

**Architecture:** Use only the approved Ayan masterboard as the image reference; describe the heavenly palace, adult human face, materials, and costume entirely in text so Zhixia cannot contaminate Ayan’s identity. Generate a new v03 project-bound working image from scratch with natural dawn cinematic live-action texture and larger medium-width ribbons, compare it against rejected v02 for oiliness and material realism, and preserve it non-destructively for user review before any character-card work.

**Tech Stack:** Codex built-in image generation, local image inspection, PNG metadata verification.

## Global Constraints

- Ayan is an adult woman around age 18 and 162cm tall; no childlike or chibi proportions.
- Ayan has a short round oval face, soft cheeks, slightly wide-set warm-amber almond eyes with gently lifted outer corners, short straight brows, a small natural nose bridge, slightly fuller lips, and shoulder-length layered ink-black hair with pale-ink tips.
- Preserve brush-tip cat ears, exactly one open S-shaped ink tail, warm amber eyes, central cinnabar forehead mark, paper-white/ink/gold motifs.
- Costume uses an ivory shallow sweetheart strapless bodice and exactly two medium-width upper-arm ink-tip ribbons, each about two-thirds of Zhixia’s ribbon width; no deep V, exaggerated cleavage, or duplicated Zhixia costume.
- Skin must be naturally matte with restrained pores, fine facial hair, and slight color variation; hair, satin, and chiffon must show dry physical texture without beauty-filter glow, plastic shine, or game-render polish.
- Full body, both hands, both shoes, both ears, and the full tail must be visible in a 9:16 composition.
- No text, card layout, border, watermark, other character, animal, prop, weapon, extra limb, extra ear, or extra tail.

---

### Task 1: Generate and inspect the working main image

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg`
- Rejected comparison only, never an image-generation input: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v01.png`
- Rejected material comparison only, never an image-generation input: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v02.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v03.png`

**Interfaces:**
- Consumes: one local Ayan identity reference plus the approved written design.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect both references**

Open the Ayan masterboard and confirm the brush-tip ears, single ink tail, amber eyes, cinnabar mark, paper-white body, pale ink texture, and warm-gold spiral cloud motif. Do not provide any Zhixia, v01, or v02 image to the generator. Open rejected v02 only after v03 generation for a visual material-and-lighting comparison.

- [ ] **Step 2: Generate one main-image candidate**

Use the built-in image generator with both references and this production prompt:

```text
Use case: identity-preserve
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project
Input image: Image 1 is the only image reference and is the authoritative identity and markings source for Ayan. No Zhixia image is provided. Build the adult human face, heavenly-palace atmosphere, fabric quality, and Latin-dance styling from the written description only.

Primary request: Transform Ayan from Image 1 into her temporary adult human form used only in the heavenly-palace series. She is an East Asian adult woman around age 18, 162cm tall, petite and light with natural adult proportions and narrow shoulders. Preserve Ayan’s calm, bright, agile personality and give her a genuinely independent human identity.

Identity invariants: exactly two upward-outward brush-tip cat ears integrated naturally with the hair; exactly one open S-shaped ink tail growing clearly from the tailbone, never forked or detached; bright warm amber eyes; one small fixed cinnabar-red mark centered on the forehead; paper-white, pale ink dry-brush, and pale warm-gold spiral-cloud visual language. No ordinary round cosplay ears, no human-ear emphasis, no second tail.

Hair and face: short round oval adult East Asian face with soft cheeks; slightly wide-set warm-amber almond eyes with gently lifted outer corners; short straight brows; a small natural nose bridge; slightly fuller lips; innocent, friendly, lively expression without childish anatomy. Deep ink-black shoulder-length layered hair with subtle pale-ink gradient tips, only a tiny pale-gold cloud-pattern side hairpin and one small cinnabar accent. No long straight half-down hair, high bun, crown, narrow elongated face, narrow-set eyes, or facial resemblance to Zhixia.

Costume: elegant ivory-white adult Latin dance costume. A secure shallow sweetheart strapless bodice fully covers and supports the chest, with restrained pale-ink dry-brush edging, no deep V and no exaggerated cleavage. An asymmetric fitted dance skirt opens from the waist, longest point at mid-calf and shorter side still covering the upper thigh. One restrained pale warm-gold spiral-cloud motif crosses the waist and skirt. Exactly two medium-width ink-tip cloud ribbons, one fixed to the back-outer side of each upper arm; each is about two-thirds the width of Zhixia’s broad ribbons and begins wider at the upper arm before tapering into a brush-tip end. Translucent paper-white chiffon gradually fades to pale ink at the tips, with one fine pale-gold edge, ending at the lower-mid calf without touching the floor. Ivory 4.5cm stable Latin heels.

Pose and composition: single character, full body in a vertical 9:16 frame; front view turned slightly three-quarter, natural weight on one foot and the other toe lightly touching as a cha-cha preparation pose; one hand naturally open and the other held near but outside the waist. Show the entire head, both brush-tip ears, both hands, both shoes, and the full single tail. Keep the two ribbons visually separated from arms, torso, skirt, legs, and tail.

Scene and style: warm-gold dawn heavenly palace, luminous cloud sea and pale jade steps, simple depth without distracting figures. Natural-light live-action period-film photography, not game illustration or glossy CG. Side-front morning light illuminates the face neutrally while warm gold remains mainly in the background and rim light. Naturally matte adult skin with restrained visible pores, fine facial hair, and slight skin-tone variation; small realistic catchlights and natural eyeball structure; individual hair strands and flyaways without oily clumps; matte woven silk-satin bodice and dry lightweight translucent chiffon. Subtle film grain and realistic lens depth of field. No beauty filter, creamy skin, porcelain skin, water-glow makeup, excessive HDR, global bloom, plastic fabric, liquid chiffon, or oily highlights.

Avoid: child, minor, chibi, doll face, sexualized juvenile, exaggerated bust, deep neckline, Zhixia face, Zhixia crown, copied Zhixia dress, wide pure-white arm drapes, extra person, animal, text, character-sheet layout, watermark, border, weapon, prop, collar, bell, paws, cat nose, whiskers, body fur, extra fingers, fused hands, extra limbs, missing limbs, extra ears, round ears, extra tail, split tail, looped tail, detached tail, ribbons fused into the body or legs.
```

- [ ] **Step 3: Persist the generated candidate in the workspace**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v03.png` without overwriting v01 or v02.

- [ ] **Step 4: Verify image metadata and perform visual QA**

Verify the saved file is a readable portrait PNG. Inspect it at full resolution and confirm the adult proportions, short round face, wide-set amber almond eyes, shoulder-length layered hair, exactly two brush-tip ears, one connected S-shaped tail, cinnabar mark, shallow sweetheart bodice, exactly two medium-width tapering ink-tip ribbons, complete hands and shoes, and absence of text or other figures. Compare v03 with rejected v02 and reject v03 if skin still looks oily or overly smooth, hair forms glossy blocks, fabric looks plastic, facial highlights bloom, or the image reads as game illustration rather than live-action film. If a structural invariant fails, run one targeted image-edit iteration changing only the failed item and re-inspect.

- [ ] **Step 5: Commit the approved working candidate only after visual inspection**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v03.png
git commit -m "生成阿砚天宫限定人形主图"
```
