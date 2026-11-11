# Zhixia Unfinished Avatar Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Generate and verify a dedicated WeChat profile avatar for the renamed account `栀夏未完成`.

**Architecture:** Use two approved local Zhixia portraits only as identity references, then generate one square head-and-shoulders portrait from the approved visual specification. Preserve the original output and create a 200×200 review copy so both full-size and real display-scale quality can be checked.

**Tech Stack:** OpenAI ImageGen, local image inspection, macOS `sips`

## Global Constraints

- The account name is `栀夏未完成`.
- The avatar is a 1:1 near-front head-and-shoulders portrait with the face occupying about 75% of the frame.
- Preserve Zhixia's chestnut wavy hair, warm facial features, pearl earrings, and muted mist-blue clothing.
- Use a warm off-white background with one broad low-contrast incomplete pale-blue arc.
- Keep all important elements inside the central 80% circular-crop safe area.
- Do not include text, letters, logos, watermarks, brands, complex scenery, or other people.

---

### Task 1: Generate the master avatar

**Files:**
- Consume: `assets/wechat_mp/virtual-lifestyle/2026-08-11-早晨留一点时间给流星雨/02-栀夏清晨作者卡.png`
- Consume: `assets/wechat_mp/virtual-lifestyle/你好我是栀夏/01-通勤.png`
- Create: `assets/wechat_mp/brand/zhixia-unfinished/avatar-master.png`

**Interfaces:**
- Consumes: two approved local identity references and the global visual constraints.
- Produces: one square high-resolution PNG master avatar.

- [x] **Step 1: Generate one avatar candidate**

  Use ImageGen with both identity references. Request stable facial identity, a near-front head-and-shoulders crop, natural skin texture, restrained smile, muted mist-blue top, warm off-white background, and a broad incomplete pale-blue arc behind the head.

- [x] **Step 2: Store the generated master**

  Save the selected output as `assets/wechat_mp/brand/zhixia-unfinished/avatar-master.png` without adding text or a watermark.

- [x] **Step 3: Inspect the master at full size**

  Confirm that the result matches the existing Zhixia identity, contains no extra people or text, and does not resemble a generic customer-service avatar.

### Task 2: Verify small-size and circular-crop behavior

**Files:**
- Consume: `assets/wechat_mp/brand/zhixia-unfinished/avatar-master.png`
- Create: `assets/wechat_mp/brand/zhixia-unfinished/avatar-200.png`

**Interfaces:**
- Consumes: the accepted master PNG.
- Produces: a 200×200 PNG for visual verification at WeChat display scale.

- [x] **Step 1: Create the 200×200 review copy**

  Run:

  ```bash
  sips -z 200 200 assets/wechat_mp/brand/zhixia-unfinished/avatar-master.png \
    --out assets/wechat_mp/brand/zhixia-unfinished/avatar-200.png
  ```

  Expected: a 200×200 PNG without aspect-ratio distortion.

- [x] **Step 2: Inspect the 200×200 output**

  Confirm that the eyes, face, chestnut hair, pearl earrings, and mist-blue color remain legible; the pale-blue arc remains secondary; and a centered circular crop would not cut the head or chin.

- [x] **Step 3: Report the deliverables**

  Provide clickable links to both PNG files and state any remaining platform-side action separately. Do not change the live public-account name or avatar in this task.
