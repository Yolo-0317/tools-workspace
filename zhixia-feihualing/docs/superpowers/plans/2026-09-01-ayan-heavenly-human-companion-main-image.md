# 阿砚天宫限定人形小女伴主图 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate one 9:16 full-body main image of Ayan’s adult heavenly-palace human form for later dual-female Latin dance videos.

**Architecture:** Use only the approved Ayan masterboard as the image reference; describe the heavenly palace, adult human face, materials, costume, broad ink-tip ribbons, and cloud-toe dance shoes entirely in text so Zhixia cannot contaminate Ayan’s identity. Generate a new v04 project-bound working image from scratch with natural dawn cinematic live-action texture, compare it against rejected v03 for ribbon width, garment ink distribution, footwear, and material realism, and preserve it non-destructively for user review before any character-card work.

**Tech Stack:** Codex built-in image generation, local image inspection, PNG metadata verification.

## Global Constraints

- Ayan is an adult woman around age 18 and 162cm tall; no childlike or chibi proportions.
- Ayan has a short round oval face, soft cheeks, slightly wide-set warm-amber almond eyes with gently lifted outer corners, short straight brows, a small natural nose bridge, slightly fuller lips, and shoulder-length layered ink-black hair with pale-ink tips.
- Preserve brush-tip cat ears, exactly one open S-shaped ink tail, warm amber eyes, central cinnabar forehead mark, paper-white/ink/gold motifs.
- Costume uses an ivory shallow sweetheart strapless bodice, restrained pale ink at both side waists, a diagonal smoke-ink gradient covering about one third of the skirt, and exactly two broad upper-arm ink-tip ribbons with the same width as Zhixia’s ribbons; no deep V, exaggerated cleavage, or duplicated Zhixia costume.
- Footwear is a closed-toe ivory cloud-toe dance shoe with a subtle upturned toe, pale-gold crossed ankle ties, matte woven satin, pale ink dry-brush and warm-gold spiral-cloud details, and an approximately 3.5cm concealed low curved heel; no modern strappy Latin sandal, exposed toe, metal buckle, patent leather, stiletto, thick platform, or exaggerated opera shoe.
- Skin must be naturally matte with restrained pores, fine facial hair, and slight color variation; hair, satin, and chiffon must show dry physical texture without beauty-filter glow, plastic shine, or game-render polish.
- Full body, both hands, both shoes, both ears, and the full tail must be visible in a 9:16 composition.
- No text, card layout, border, watermark, other character, animal, prop, weapon, extra limb, extra ear, or extra tail.

---

### Task 1: Generate and inspect the working main image

**Files:**
- Reference: `zhixia-feihualing/assets/characters/阿砚角色母板高写实CG-v01-最终版-Seedance上传版.jpg`
- Rejected comparison only, never an image-generation input: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v01.png`
- Rejected material comparison only, never an image-generation input: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v02.png`
- Rejected width, ink-distribution, and footwear comparison only, never an image-generation input: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v03.png`
- Create: `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04.png`

**Interfaces:**
- Consumes: one local Ayan identity reference plus the approved written design.
- Produces: one PNG candidate for user visual approval; it is not yet a formal character masterboard.

- [ ] **Step 1: Inspect the sole identity reference**

Open the Ayan masterboard and confirm the brush-tip ears, single ink tail, amber eyes, cinnabar mark, paper-white body, pale ink texture, and warm-gold spiral cloud motif. Do not provide any Zhixia, v01, v02, or v03 image to the generator. Open rejected v03 only after v04 generation for a visual comparison of ribbon width, garment ink distribution, footwear, and material realism.

- [ ] **Step 2: Generate one main-image candidate**

Use the built-in image generator with the Ayan masterboard as the only image reference and this production prompt:

```text
Use case: identity-preserve
Asset type: 9:16 full-body character main image for a Chinese fantasy dance-video project
Input image: Image 1 is the only image reference and is the authoritative identity and markings source for Ayan. No Zhixia image is provided. Build the adult human face, heavenly-palace atmosphere, fabric quality, and Latin-dance styling from the written description only.

Primary request: Transform Ayan from Image 1 into her temporary adult human form used only in the heavenly-palace series. She is an East Asian adult woman around age 18, 162cm tall, petite and light with natural adult proportions and narrow shoulders. Preserve Ayan’s calm, bright, agile personality and give her a genuinely independent human identity.

Identity invariants: exactly two upward-outward brush-tip cat ears integrated naturally with the hair; exactly one open S-shaped ink tail growing clearly from the tailbone, never forked or detached; bright warm amber eyes; one small fixed cinnabar-red mark centered on the forehead; paper-white, pale ink dry-brush, and pale warm-gold spiral-cloud visual language. No ordinary round cosplay ears, no human-ear emphasis, no second tail.

Hair and face: short round oval adult East Asian face with soft cheeks; slightly wide-set warm-amber almond eyes with gently lifted outer corners; short straight brows; a small natural nose bridge; slightly fuller lips; innocent, friendly, lively expression without childish anatomy. Deep ink-black shoulder-length layered hair with subtle pale-ink gradient tips, only a tiny pale-gold cloud-pattern side hairpin and one small cinnabar accent. No long straight half-down hair, high bun, crown, narrow elongated face, narrow-set eyes, or facial resemblance to Zhixia.

Costume: elegant ivory-white adult Latin dance costume. A secure shallow sweetheart strapless bodice fully covers and supports the chest, with restrained pale-ink dry-brush edging, no deep V and no exaggerated cleavage. Keep the center front of the bodice bright ivory and place restrained pale-ink washes only on both side-waist areas. An asymmetric fitted dance skirt opens from the waist, longest point at mid-calf and shorter side still covering the upper thigh. Create one diagonal ink gradient from one side waist toward the opposite skirt hem, with about one third of the skirt in smoke-ink gray; place one restrained pale warm-gold spiral-cloud motif along the boundary between white and ink. Exactly two broad ink-tip cloud ribbons, one fixed to the back-outer side of each upper arm; both have the same generous width as Zhixia’s broad celestial ribbons, beginning fully broad at the upper arm and tapering only near the dense ink brush-tip ends. Each ribbon transitions from translucent paper-white chiffon through smoke-ink gray to a clearly dark ink brush-tip, with one fine pale-gold edge, ending at the lower-mid calf without touching the floor. Keep both ribbons separate from the body, skirt, legs, and tail. Keep the dark tail distinct from all garment ink.

Footwear: ivory closed-toe celestial cloud-toe dance shoes, with only a subtle upward curve at the toe and no exaggerated opera silhouette. Matte woven satin with pale-ink dry-brush marks and restrained pale warm-gold spiral-cloud embroidery. Keep the instep moderately open for a long dance leg line and secure each ankle with pale-gold crossed ties. Use an approximately 3.5cm concealed low curved heel that supports cha-cha weight changes and forefoot pressure. The shoes must read as celestial dance footwear, never as modern strappy Latin sandals.

Pose and composition: single character, full body in a vertical 9:16 frame; front view turned slightly three-quarter, natural weight on one foot and the other toe lightly touching as a cha-cha preparation pose; one hand naturally open and the other held near but outside the waist. Show the entire head, both brush-tip ears, both hands, both shoes, and the full single tail. Keep the two ribbons visually separated from arms, torso, skirt, legs, and tail.

Scene and style: warm-gold dawn heavenly palace, luminous cloud sea and pale jade steps, simple depth without distracting figures. Natural-light live-action period-film photography, not game illustration or glossy CG. Side-front morning light illuminates the face neutrally while warm gold remains mainly in the background and rim light. Naturally matte adult skin with restrained visible pores, fine facial hair, and slight skin-tone variation; small realistic catchlights and natural eyeball structure; individual hair strands and flyaways without oily clumps; matte woven silk-satin bodice and dry lightweight translucent chiffon. Subtle film grain and realistic lens depth of field. No beauty filter, creamy skin, porcelain skin, water-glow makeup, excessive HDR, global bloom, plastic fabric, liquid chiffon, or oily highlights.

Avoid: child, minor, chibi, doll face, sexualized juvenile, exaggerated bust, deep neckline, Zhixia face, Zhixia crown, copied Zhixia dress, narrow ribbons, pure-white ribbon tips, garment ink covering the center chest, garment ink fused with the tail, modern strappy Latin sandals, exposed toes, metal shoe buckles, patent leather, stilettos, thick platforms, exaggerated opera shoes, extra person, animal, text, character-sheet layout, watermark, border, weapon, prop, collar, bell, paws, cat nose, whiskers, body fur, extra fingers, fused hands, extra limbs, missing limbs, extra ears, round ears, extra tail, split tail, looped tail, detached tail, ribbons fused into the body or legs.
```

- [ ] **Step 3: Persist the generated candidate in the workspace**

Copy the selected built-in output to `zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04.png` without overwriting v01, v02, or v03.

- [ ] **Step 4: Verify image metadata and perform visual QA**

Verify the saved file is a readable portrait PNG. Inspect it at full resolution and confirm the adult proportions, short round face, wide-set amber almond eyes, shoulder-length layered hair, exactly two brush-tip ears, one connected S-shaped tail, cinnabar mark, shallow sweetheart bodice, pale-ink side waists, diagonal smoke-ink covering about one third of the skirt, exactly two broad tapering ink-tip ribbons with the same visual width as Zhixia’s, complete hands, and closed cloud-toe dance shoes with crossed ankle ties and a concealed low heel. Confirm the chest center stays ivory, the tail stays separate from garment ink, and there is no text or other figure. Compare v04 with rejected v03 and reject v04 if the ribbons are still narrow, the clothing lacks smoke-ink weight, shoes read as modern sandals, skin looks oily or overly smooth, hair forms glossy blocks, fabric looks plastic, facial highlights bloom, or the image reads as game illustration rather than live-action film. If a structural invariant fails, run one targeted image-edit iteration changing only the failed item and re-inspect.

- [ ] **Step 5: Commit the approved working candidate only after visual inspection**

```bash
git add -f zhixia-feihualing/assets/characters/work/阿砚天宫限定人形小女伴主图-v04.png
git commit -m "生成阿砚天宫限定人形主图"
```
