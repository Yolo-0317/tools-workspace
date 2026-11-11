# 中文逐句复核工具 Implementation Plan

> 本任务由当前 agent 在本会话实现；用户已要求脚本遍历每句并交给 agent 复核，不另设交接审批。

**Goal:** 冻结文章，生成可核对的句子清单，让 agent 逐条审核，并阻止漏句、错版或只有笼统评价的结果被当作完成。

**Architecture:** Python标准库脚本提供prepare、run、check三个命令。切分、文件哈希和结果覆盖由程序负责，语法、口吻及上下文判断由agent负责；生成建议和报告，不直接覆盖文章。run调用本机Codex CLI的只读、临时会话，沿用配置模型，不引入新API凭据。prepare产物也可交给当前会话的agent填写结果，随后由check验收。

**Tech Stack:** Python 3标准库、unittest、已安装Codex CLI。通用脚本放scripts，不依赖公众号生成客户端的专属工作目录和环境变量。

## Global Constraints

- 原文按字符区间保留，非空白字符不能漏掉；标题、无句号短段、列表和代码片段也登记。
- URL、Markdown引用、小数、引号及省略号不按普通标点胡乱拆开。机械切分是句子候选，不冒称语言学解析。
- 每句携带原段、前后段与全文；根据实际文字召回本地搭配语料，冻结规则与证据快照。
- 每句必须分别交语法、口吻和承接结论及理由；无问题明确保留，有疑点可标待核，不为覆盖率强改。
- 结果绑定文章、manifest及批次；漏句、重句、未知ID、原句不符、过期文件或缺检查维度均不放行。
- 不自动修改文章，不无限重试，不推稿，不发送消息或创建调度。

## Task 1: 冻结、切分与覆盖校验

Files: scripts/chinese_sentence_review.py; scripts/tests/test_chinese_sentence_review.py。

- [x] 写并运行失败测试：真实Markdown中的短句、角标URL、小数、引号、省略号、标题及无句号末段能被覆盖，且区间与原文一致。
- [x] 实现切分和prepare；为原文、规则、语料和任务生成hash，按批输出包含上下文与可用语料的prompt。
- [x] 写并运行失败测试：漏句、重复、错原句、错版本及缺维度结果被拒绝；输入改动后旧审核失效。
- [x] 实现逐条校验及check，生成逐句Markdown记录和JSON覆盖状态。

## Task 2: agent调用、真实试跑与接入说明

Files: scripts/chinese_sentence_review.py; docs/writing/逐句复核工具.md; .cursor/skills/wechat-mp-article/references/sentence-grammar.md。

- [x] 写CLI行为测试，验证不覆盖非空目录、错误状态退出码和建议不自动覆盖原文。
- [x] 实现run：有限超时、严格JSON输出、有效批次续跑，错误不计作通过。
- [x] 跑相关单元测试；给当前六年级文章prepare，实际让agent复核生成批次，再用check核清全部覆盖。
- [x] 文档写清命令、产物、失败及继续方式；公众号逐句记录入口仅加工具链接，不复制中文基座规则。
