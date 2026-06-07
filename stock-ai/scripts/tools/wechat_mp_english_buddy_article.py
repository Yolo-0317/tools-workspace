#!/usr/bin/env python3
"""公众号工作区稿变体：English Buddy 少儿英语语音带读。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

VARIANT = "english_buddy"

_REPO_ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_THUMB_LOCAL = _REPO_ROOT / "assets" / "wechat_mp" / "inline" / "inline-ai-tech.jpg"
_ENGLISH_BUDDY_THUMB_CACHE = _REPO_ROOT / "data" / "wechat_mp_thumb_english_buddy.json"


def english_buddy_article_title() -> str:
    return "给娃做英语带读，不想再开第三个会员 App"


def english_buddy_article_digest() -> str:
    return (
        "在家用浏览器给娃英语带读：本地听写 + 小模型 + 语音合成，"
        "按句推进、能打断；内置/自贴课文、预热缓存，跟读有三色发音反馈。"
    )[:128]


def english_buddy_recommended_hashtags() -> list[str]:
    return ["本地AI", "家庭自动化", "给娃省事", "英语跟读", "亲子英语"]


def english_buddy_architecture_diagram() -> str:
    return """```text
手机 / 平板浏览器
  │ 开麦，16kHz 音频流
  ▼
家庭服务器（Mac 或 PC）
  ├─ 本地听写 (Whisper small，约 461MB)
  ├─ 对话小模型 (Ollama qwen2.5:3b)
  └─ 语音合成 (edge-tts 或离线 piper)
  │
  ▼
扬声器播放 ◄── 娃开口 ──► 打断老师，进入下一句
```"""


def english_buddy_read_along_flow() -> str:
    return """```text
选年级、选课文 → 点「开始带读」
  → 这课在当前老师+语速下预热好了吗？
       ├─ 否 → 列表不出现，或提示先预热
       └─ 是 → 老师念第 1 句
              → 可跟读账号：开麦 → 听写 → 可选发音提示
              → 只听账号：不采麦，只听
  → 一句一句往下；读完自己换课，不自动跳下一篇
```"""


def pick_english_buddy_workspace_thumb(
    *,
    force_reupload: bool = False,
) -> tuple[str | None, dict[str, Any] | None]:
    """上传 inline-ai-tech.jpg 作 workspace 封面（带 md5 缓存）。"""
    path = WORKSPACE_THUMB_LOCAL
    if not path.is_file():
        return None, {"errcode": -1, "errmsg": f"封面文件不存在: {path}"}

    from scripts.tools.wechat_mp_client import add_permanent_image

    cache_key = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    if not force_reupload and _ENGLISH_BUDDY_THUMB_CACHE.is_file():
        try:
            cached = json.loads(_ENGLISH_BUDDY_THUMB_CACHE.read_text(encoding="utf-8"))
            if cached.get("cache_key") == cache_key and cached.get("media_id"):
                return str(cached["media_id"]), None
        except (json.JSONDecodeError, OSError):
            pass

    media_id, err = add_permanent_image(path)
    if err or not media_id:
        return None, err or {"errcode": -1, "errmsg": "上传 English Buddy 封面失败"}

    _ENGLISH_BUDDY_THUMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _ENGLISH_BUDDY_THUMB_CACHE.write_text(
        json.dumps(
            {"cache_key": cache_key, "media_id": media_id, "source": str(path)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return media_id, None


def generate_english_buddy_article_body() -> str:
    return f"""给娃练英语口语，市面上的 App 试下来总觉得差点意思：会员一层套一层，界面像聊天室，很难老老实实跟读一句句课文。有些产品「打电话」形态做得不错，但对话一多就飘，不适合 4 岁左右、字还认不全的小朋友。

后来在家里的 Mac 上搭了一页浏览器语音——选课文、老师慢慢念、娃说得不对可以打断重来。听写、对话、合成都在本机跑，不上传录音。下面按「为什么做、怎么跑、踩什么坑」说清楚，方便同样想给娃省会员、又愿意折腾本地 AI 的读者对照。

> 和会员 App 差在哪

商业 App 常见两条路：要么是题库 + 打卡，要么是 AI 闲聊。带读需要的是第三种——**按句推进**：老师念一句，娃跟一句，节奏可控，语速能调慢，外放被麦克风拾取时还能打断重来。

本地搭的好处也直白：**隐私**（语音不出家门）、**成本**（模型下载一次，后面主要是电费和硬盘）、**可改**（课文可以自己贴，幼儿园研学短文、绘本片段都能进列表）。代价是得有一台常开的家庭机器，以及愿意处理 HTTPS、预热这类「工程师父母」才碰的琐事。

> 整体长什么样

{english_buddy_architecture_diagram()}

浏览器只负责界面和采麦；重活在后端：听写用 faster-whisper，老师台词用 Ollama 出短句（面向幼儿，不长篇大论），再合成语音推回手机。带读和自由聊天共用一条长连接，只是模式不同——带读有课文进度，闲聊没有。

> 一次带读 session 怎么走

{english_buddy_read_along_flow()}

首页大致是这样——选老师、年级、课文和语速，再点「开始带读」：

[[fig:english-buddy-home.jpg|max-h=480;fit=contain]]

界面侧：可选艾莎、奥特曼两套皮肤，换的是音色和画面，底层逻辑一样。内置课文按年级筛；自己贴的课文要登录保存，换老师或语速得先把语音预热进缓存，否则列表里看不到，或者首句卡两三秒。

权限上做了区分：只有少数家庭账号能开麦跟读，别的账号只能听老师念——适合「一个娃跟读、另一个先旁听」的场景。同时带读限两路，避免 Whisper 占满 CPU。「自由聊天」只对少数账号开放：首页有没有按钮、后端让不让进，都会再看登录身份，避免访客误进闲聊。

> 课文从哪来

内置课文按沪教牛津年级编排。进首页先选年级，列表里是当前「老师 + 语速」已经预热好的课——没缓冲完的课不会露出来，避免娃点进去干等。

登录后可以贴自己的课文：幼儿园研学短文、老师布置的句子、绘本里抠出来的段落都行。自定义课和账号绑定，只有自己能看到；换艾莎 / 奥特曼或调慢语速，都要按新组合重新预热，进度走完后才会回到可选列表。

> 发音三色怎么评

跟读账号开麦后，本地听写把娃说的话转成文字，再和屏幕上的当前句比对——不另开云端打分模型，规则就在本机跑。

· **绿（过关）**：词对上了，顺序也基本对，提示可以跳下一句  
· **黄（差一点）**：大意思听到了，个别词漏掉或顺序有点乱，鼓励再读一遍  
· **橙（重来）**：差得比较多，建议听老师再念一次当前句  

默认是「温柔模式」：三色只做视觉反馈，**不会因为判橙就卡死不能跳下一句**——4 岁娃如果一错就停，很容易腻。真想要「不绿不让过」也可以切严格模式，一般家庭用默认就够。页面上若开了带读反馈，句旁会有绿 / 黄 / 橙图例；只听不跟读的账号看不到这套比对。

带读页长这样——课文逐句高亮，标题栏写「绿过关 · 黄接近 · 橙再练」，底部有上一句 / 再说一遍 / 我说完啦：

[[fig:english-buddy-readalong.jpg|max-h=520;fit=contain]]

> 本地跑起来要什么

· 机器：Apple Silicon Mac 或同等 CPU 即可；Whisper small 内存占用可控，并行两路带读是现实上限  
· 听写：faster-whisper small 首次约 461MB，可换更小模型换速度  
· 对话：Ollama 拉 qwen2.5:3b 量级就够，不必上大模型  
· 合成：默认 edge-tts 要联网；想全离线可切 piper  
· 浏览器：Chrome / Safari 均可；**手机必须用 HTTPS**，否则 Safari 不给麦克风  

和开源项目 HiKid、Magic English Buddy 同类：都是「听 → 想 → 说」闭环。差异在于这边更偏**课文带读**——有年级、有逐句进度、有预热缓存，而不是纯聊天室。

> 三个最容易踩的坑

**内网只能填 IP。** 公网证书盖不住局域网地址。家里 WiFi 若解析不了域名，就得给 IP 单独挂 HTTPS（自签或 mkcert），手机装一次根证书，否则进带读就弹回首页。

**一进页面就要麦克风。** 若在授权完成前就开播，HTTP 下失败会直接退出。改成先接通会话，麦要不到就降级「只听」，页面上写清楚，家长才不会以为「坏了」。

**换老师或语速没预热。** 语音合成是按「课文 + 老师 + 语速」写缓存的。条件一变就要重新预热，否则列表缺课或首句卡顿——这和视频要先缓冲是同一道理。

> 适合谁、不适合谁

适合：家里已有 NAS / Mac 常开、愿意贴自己的课文、重视隐私、娃 3～7 岁需要**慢速跟读**的家庭。不适合：想零配置开箱、不想碰 HTTPS 和预热的用户——这类仍用商业 App 更省心。

若你也在搭本地语音 + 小模型，手机 HTTPS 或 mkcert 那一步最容易卡，需要的话可以单拆一篇写清楚。"""