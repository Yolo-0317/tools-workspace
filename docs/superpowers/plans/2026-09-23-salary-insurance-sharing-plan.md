# 工薪家庭保险分享稿 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成一篇面向月收入约 8000 元工薪读者的公众号文章，帮助其理解医疗险、重疾险和定期寿险的功能及购买顺序。

**Architecture:** 先用监管与医保部门公开材料锁定基本医保和三类商业保险的功能边界，再以一个预算有限的工薪家庭为观察对象组织正文。成稿后分别检查事实边界、分享式口吻、金融合规和去 AI 味，不推荐具体公司或产品。

**Tech Stack:** 官方公开网页、公众号非虚构写作规范、人工逐段朗读检查。

## Global Constraints

- 主标题为《月薪8000，医疗险、重疾险和寿险该先买哪个？》。
- 正文约 900—1100 字，纯段落，不设小标题和编号。
- 不推荐保险公司、具体产品、统一保额或固定保费比例。
- 不虚构投保、理赔、咨询或采访经历。
- 基本医保是保障底座，商业健康保险承担补充作用。
- 具体保障责任以合同为准，健康告知只提醒如实填写，不作核保或疾病判断。
- 不添加运营关注句，由排版阶段处理。

---

### Task 1: 建立保险功能证据卡

**Files:**
- Read: `docs/superpowers/specs/2026-09-23-salary-insurance-sharing-design.md`
- Create: `stock-ai/output/salary_insurance_evidence_20260923.md`

**Interfaces:**
- Consumes: 国家医保局关于基本医保主体地位和商业健康保险补充作用的公开说明；金融监管部门关于保险适当性和合同核对事项的消费提示。
- Produces: 供正文使用的事实清单，逐项标注来源和不可越过的表达边界。

- [ ] **Step 1: 记录已核实的制度定位**

写明基本医保是多层次医疗保障体系的主体、基础和底座，商业健康保险用于补充基本医保之外的保障需求，并保存原始链接。

- [ ] **Step 2: 记录投保前必须核对的合同事项**

写明“保什么、保多长时间、什么情况下免责”、健康告知、等待期、免赔额、续保条件和退保损失分别属于什么判断环节；不能把通用提醒写成具体产品承诺。

- [ ] **Step 3: 检查事实边界**

逐项确认材料没有支持“某类保险人人必买”“确诊一定赔”“医疗费全部报销”“保证续保等于终身不涨价”等表述。

- [ ] **Step 4: 保存证据卡并复核链接**

Run:

```bash
rg -n "基本医保|医疗险|重疾险|定期寿险|健康告知|免责|续保" stock-ai/output/salary_insurance_evidence_20260923.md
```

Expected: 每个核心概念至少有一条说明，制度性判断均附公开来源。

### Task 2: 完成分享式正文

**Files:**
- Create: `stock-ai/output/salary_insurance_article_20260923.txt`

**Interfaces:**
- Consumes: Task 1 的证据卡和已确认的文章设计。
- Produces: 标题加 900—1100 字纯段落正文。

- [ ] **Step 1: 写开篇和读者困惑**

从“工资刚够覆盖生活，却同时面对医疗险、重疾险和寿险三个选择”切入，尽早回应“预算有限时哪份更急”，不虚构具体人物和账单。

- [ ] **Step 2: 按风险顺序推进正文**

依次解释基本医保、医疗险、重疾险和定期寿险；每一类只回答它主要解决什么问题、什么人更需要、付款前最该看什么。

- [ ] **Step 3: 写出有条件的购买顺序**

将建议限定为判断框架：先确认医保，再看大额医疗支出风险，然后根据家庭责任判断重疾险和定期寿险优先级。明确收入数字不能单独决定方案。

- [ ] **Step 4: 收束到保费承受能力**

结尾强调保险不能挤占房租、吃饭、还贷和应急储备；适合工薪家庭的方案是关键时刻能用、平时交得起，而不是险种最多。

### Task 3: 进行事实、语气和金融合规检查

**Files:**
- Modify: `stock-ai/output/salary_insurance_article_20260923.txt`

**Interfaces:**
- Consumes: Task 2 的完整正文。
- Produces: 可以交给用户审阅的最终正文。

- [ ] **Step 1: 检查金融建议边界**

搜索并删除未经条件限定的“应该买”“必须买”“最划算”“保证赔”“一定够”等措辞；保留基本医保连续有效这一制度性提醒。

- [ ] **Step 2: 检查是否像保险产品说明书**

把“保障责任、风险缺口、支付能力”等连续抽象表达改成正常说话，例如“这笔钱到底解决什么”“一年保费交下去会不会挤到日常生活”。

- [ ] **Step 3: 逐段朗读并补足口语结构**

检查“是、的、了、已经、还、就、也、才”等是否被不自然地省略；事实段保持平实，只在读者真正会追问的地方使用语气词。

- [ ] **Step 4: 检查篇幅和格式**

Run:

```bash
python3 -c "from pathlib import Path; p=Path('stock-ai/output/salary_insurance_article_20260923.txt'); t=p.read_text(); print(len(''.join(t.split())), 'chars'); print('sections', t.count(chr(10)+chr(10))+1)"
```

Expected: 正文去空白后约 900—1100 字，纯段落，无小标题、编号和运营关注句。

- [ ] **Step 5: 输出完整正文供用户核验**

正文第一行只放标题，空一行后输出文章；不附写作说明、产品推荐或发布动作。

