# 公众号对外分享资料

本目录存放可上传夸克、通过关注回复「写作」发放的读者向文档。

**范围**：AI 写作技巧、社会热点排版语气、避坑清单、微信公众平台 API 对接。  
**不含**：选题策略、流量运营、账号内部 SOP。

## 当前文件

| 文件 | 用途 | 夸克分享链接 |
|------|------|--------------|
| [牛马也智能-AI写作与公众号API笔记.md](./牛马也智能-AI写作与公众号API笔记.md) | 回复关键词「写作」发放 | `待上传后填入` |

## 上传夸克（一次性）

1. 打开 [夸克网盘](https://pan.quark.cn)，上传上述 `.md` 文件（或先转 PDF 再传，手机阅读更稳）  
2. 创建分享链接：永久有效、公开（勿设提取码，方便手机点开）  
3. 把链接填入上表，并更新 `account-packaging.md` 关键词「写作」中的 `{{QUARK_WRITING_GUIDE_URL}}`

可选 CLI（本机已配置夸克 skill 时）：

```bash
node .cursor/skills/quarkclouddrive/scripts/quark-drive.cjs upload \
  stock-ai/docs/share/牛马也智能-AI写作与公众号API笔记.md
```

## 后台配置

路径：**内容与互动 → 自动回复 → 关键词回复** · 关键词 `写作`（半匹配）

正文见 [account-packaging.md](../../../.cursor/skills/wechat-mp-drafts/account-packaging.md) §三 B
