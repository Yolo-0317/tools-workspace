# 公众号标题 Skill 简短设计与计划

## 目的

把「牛马也智能」起标题与改标题的判断集中到独立 Skill，解决商品稿标题只顾藏品牌、悬念空泛或与正文错位的问题。

## 设计

- 建立 `.cursor/skills/wechat-mp-title-writing/SKILL.md`，负责读稿、产出不同角度候选、按正文和首段选定标题。
- 复用现有 `sousou-content-rules.md` 与 `traffic-copy-craft.md` 作为平台门禁真源，不复制各稿型硬禁表。
- 健康商品广告只约束标题证据和表达；不改变 `wechat-mp-health-content` 的选品、广告审查或草稿边界。
- 在公众号导航与写作 Skill 增加入口；不修改自动标题生成代码或已有稿件。

## 实施与验证

1. 写自包含的标题 Skill，并说明触发条件和排除范围。
2. 更新两个路由入口，使「起标题／改标题／标题太差」可找到新 Skill。
3. 用 skill-creator 的 `quick_validate.py` 检查格式；手工用当前善存广告稿检验「线索、悬念、首段同题」三个判断。
