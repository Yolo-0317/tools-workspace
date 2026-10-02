# 栀夏九歌祭舞 v03 五秒测试 v02 提示词 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 从已确认设计中提取一份不含设计说明的 Seedance 5 秒 v02 可复制提示词。

**Architecture:** 独立 Markdown 文件只保存上传素材、生成设置和完整提示词，避免把验收文字误投喂给模型。文本校验检查真人误判规避开头、画面占比、睁眼要求、左右臂高度差、严格两个袖缘和写实材质约束。

**Tech Stack:** Markdown、ripgrep、Git。

## Global Constraints

- 使用纯AI原创成年虚拟角色声明，不使用真人照片或真人原型表述。
- 生成时长 5 秒、画幅 9:16、单一连续镜头。
- 人物占画面高度约 70%，从头顶到鞋履完整可见。
- 右手最终在头侧斜上方，左手始终低于胸口。
- 左右袖口后下缘合计严格两个朱红尾端。
- 不加入验收结论、首轮视频分析或内部设计术语。

---

### Task 1: 建立独立可复制提示词

**Files:**
- Create: `zhixia-feihualing/assets/prompts/jiuge/00-donghuang-taiyi-v03-5s-test-v02.md`
- Reference: `zhixia-feihualing/docs/superpowers/specs/2026-08-30-zhixia-jiuge-v03-5s-video-test-v02-prompt-design.md`

**Interfaces:**
- Consumes: 已确认设计中的“Seedance v02 完整提示词”。
- Produces: 可直接复制到 Seedance 的纯净正文。

- [x] **Step 1: 写入上传素材和生成设置**

文件开头只记录唯一上传图、5 秒、9:16 和单一连续镜头，不混入首轮 QA 结论。

- [x] **Step 2: 写入冻结提示词正文**

从设计规格完整提取虚拟角色声明、构图、动作、露脸、材质和禁止项，保持左右臂终点及两个袖缘约束不变。

- [x] **Step 3: 校验关键约束**

运行：

```bash
rg -n "纯AI生成的原创成年虚拟角色|占画面高度约70%|自然睁眼|右手始终不过头顶|左手始终低于胸口|严格两个|不得生成可辨识人声" zhixia-feihualing/assets/prompts/jiuge/00-donghuang-taiyi-v03-5s-test-v02.md
git diff --check -- zhixia-feihualing/assets/prompts/jiuge/00-donghuang-taiyi-v03-5s-test-v02.md
```

预期：七类约束全部命中，格式检查无输出。

- [x] **Step 4: 提交复制版**

```bash
git add zhixia-feihualing/assets/prompts/jiuge/00-donghuang-taiyi-v03-5s-test-v02.md
git commit -m "整理九歌五秒测试复制提示词"
```
