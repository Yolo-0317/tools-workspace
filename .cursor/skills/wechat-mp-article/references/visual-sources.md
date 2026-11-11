# 配图方法来源

2026-10-09核对以下原作者 GitHub 文件，独立整理为本地艺术配图流程。只采用设计方法，没有安装这些仓库或运行其脚本；外部文件不是运行时依赖。能力描述属于仓库说明，不代表本地已验证各模型、全部风格或生成质量。

| Skill 与原文件 | 借鉴的内容 | 采用范围与调整 |
| --- | --- | --- |
| [huashu-wechat-image](https://github.com/alchaincyf/huashu-skills/blob/master/huashu-wechat-image/SKILL.md) | 封面、插图、信息图分工，生成/原生绘制双路径，系列与裁切检查 | 读取入口、配图规划与验收相关段落；不沿用固定Gemini、图床、每节一图、多阶段审批和固定文字上限。 |
| [huashu-gpt-image](https://github.com/alchaincyf/huashu-gpt-image/blob/master/SKILL.md) | 提示词落实主体、媒介与视觉参考；参考图保持风格；按失败原因修正 | 读取提示词约束、参考陷阱、单图流程和失败表；不依赖花叔私有角色/素材库，不以品牌名代替具体画面，不采用仓库模型能力宣称作保证，也不自动探索生成5—10张。 |
| [huashu-art-motion](https://github.com/alchaincyf/huashu-art-motion/blob/main/SKILL.md)及[风格索引](https://github.com/alchaincyf/huashu-art-motion/blob/main/references/%E9%A3%8E%E6%A0%BC%E9%85%8D%E6%96%B9/INDEX.md) | 艺术流派的材质、笔触、色板、光影与主体统一；先设计一帧 | 读完整入口及风格索引，未读全部配方；静态配图仅借鉴视觉特征，真正要动画才调用动画流程，不强制视频、语音和三方向试片。 |
| [huashu-design](https://github.com/alchaincyf/huashu-design/blob/master/SKILL.md) | HTML原生设计与信息图导出，视觉层次和设计评审 | 核对仓库README能力与工具说明；仅作为精确图形路线候选，未采用整份系统或全部设计库。 |
| [baoyu-article-illustrator](https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-article-illustrator/SKILL.md)及[风格库](https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-article-illustrator/references/styles.md) | 图的内容形式、画风、配色分开组合；先选插入位置，保存每图提示词，系列一致 | 读取入口分析、类型/风格/配色、规划与生成部分及风格表/匹配表；不默认手绘信息卡，不强制配置文件/反复确认，不照搬其CLI和批处理参数。 |
| [baoyu-cover-image](https://github.com/JimLiu/baoyu-skills/blob/main/skills/baoyu-cover-image/SKILL.md) | 封面按主体形式、色板、渲染、文字量、情绪分别设计 | 读取入口维度、内容分析、提示词与参考规则；封面可以无字，不照搬全部样式目录、配置问卷和固定尺寸，不自动安装生成后端。 |

水彩、丝网印刷、科技蓝图等选择来自上述风格方法；纸雕、木刻、绘画光影等是根据用户艺术配图需求形成的本地设计方向，不声称每项都已由上游或本地实图验证。最终效果仍需实际生成、打开图片及手机尺度验收。
