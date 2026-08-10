#!/usr/bin/env python3
"""公众号临时稿变体：HarryPutter 哈利波特句级带读。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

VARIANT = "harryputter"

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WORKSPACE_ROOT = _REPO_ROOT.parent
HARRYPUTTER_THUMB_LOCAL = _WORKSPACE_ROOT / "harryputter" / "picture" / "harryputter.jpeg"
_THUMB_CACHE = _REPO_ROOT / "data" / "wechat_mp_thumb_harryputter.json"


def harryputter_article_title() -> str:
    return "HarryPutter：哈利波特听书能对到每一句吗？"


def harryputter_article_digest() -> str:
    return (
        "哈利波特句级听读 HarryPutter：本地 Whisper 转写、词流对齐电子书分句，"
        "浏览器播到哪亮哪句；中文对照表人工维护，文本与音频自备，代码可复用。"
    )[:128]


def harryputter_recommended_hashtags() -> list[str]:
    return ["HarryPutter", "哈利波特听读", "本地AI", "语音对齐", "Whisper"]


def harryputter_pipeline_diagram() -> str:
    return """```text
HarryPutter 离线处理
  │
电子书按章抽句子 ──┐
                  ├─ 词流单调匹配 → 每句起止时间
章节朗读音频 ── Whisper 词级时间戳 ──┘
  │
  ▼
句级清单 → 静态页 / 可添加到主屏幕
  │
  ▼
播放进度驱动：当前句高亮 + 点词词典 + 中文行
```"""


def harryputter_listen_flow() -> str:
    return """```text
HarryPutter 播放器
  选书目 → 选章 → 播放
    → 播放头落在哪句的时间窗内，哪句高亮
         ├─ 点英文词 → 侧边简明词典
         ├─ 对齐不稳 → 该行半透明（插值句）
         └─ 手机可全屏当网页应用用
    → 本章播完停止，不自动跳下一章
```"""


def pick_harryputter_thumb(*, force_reupload: bool = False) -> tuple[str | None, dict[str, Any] | None]:
    path = HARRYPUTTER_THUMB_LOCAL
    if not path.is_file():
        return None, {"errcode": -1, "errmsg": f"封面不存在: {path}"}

    from scripts.tools.wechat_mp_client import add_permanent_image

    cache_key = hashlib.md5(path.read_bytes()).hexdigest()[:16]
    if not force_reupload and _THUMB_CACHE.is_file():
        try:
            cached = json.loads(_THUMB_CACHE.read_text(encoding="utf-8"))
            if cached.get("cache_key") == cache_key and cached.get("media_id"):
                return str(cached["media_id"]), None
        except (json.JSONDecodeError, OSError):
            pass

    media_id, err = add_permanent_image(path)
    if err or not media_id:
        return None, err or {"errcode": -1, "errmsg": "上传 HarryPutter 封面失败"}

    _THUMB_CACHE.parent.mkdir(parents=True, exist_ok=True)
    _THUMB_CACHE.write_text(
        json.dumps(
            {"cache_key": cache_key, "media_id": media_id, "source": str(path)},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return media_id, None


def generate_harryputter_article_body() -> str:
    return f"""章节有声书播放器通常只给**整条时间轴**，不给**每一句的起止时间**：拖进度条只能近似到段落，很难稳定对应「音频此刻是正文哪一句」。首章本地 Whisper 转写大约 5 分钟量级，换来的句级清单才能做逐句高亮、行内查词和中英对照。

**HarryPutter**（哈利波特句级听读）把朗读音频和电子书分句锁在一起：文本和章节音频由读者自备，转写与对齐在本机跑，浏览器只负责播放和高亮。下面按架构、播放逻辑和踩坑说明，方便同类长音频 + 文本同步场景照搬。

> HarryPutter 和普通播放器差在哪

听书 App 强项是版权库、推荐和倍速，弱项是**文本与音频逐句对齐**。段落进度条导不出「第 N 句从几秒到几秒」，自然做不到播到哪亮哪句。

HarryPutter 产出的是**章级句清单**：每一行正文绑一段音频时间。播放时按当前播放位置切换高亮；对齐没把握的行半透明，表示插值或锚点偏了，别当金标准文本。

> HarryPutter 整体怎么跑

{harryputter_pipeline_diagram()}

重活在离线脚本：抽句、Whisper 转写、词流对齐、写句清单。在线侧是轻量 Python 服务挂静态页，前面可加反代。浏览器端不采麦克风，也不打分——只听、只看、点词查释义。

> 打开 HarryPutter 后发生什么

{harryputter_listen_flow()}

播放器大致长这样——逐句列表、当前句高亮，底部播放条，点词可查词典：

[[fig:harryputter-player.jpg|max-h=520;fit=contain]]

> 试读入口

[[cta:关注本公众号|回复「哈利波特」|即可试读]]

句清单里每一行有英文、起止时间、可选中文、对齐标记。词典走侧边栏，不打断音频。换章在页内完成；音频文件必须是服务目录里的实体路径，符号链接指到别处容易播不出来。

> 中文行从哪来

英文和音频由对齐脚本绑定；中文不做全书机翻。按句维护中文对照表就行：程序管时间轴，人改读起来顺的那几句。

> 本地部署 HarryPutter

· **素材**：自备电子书文本 + 分章朗读音频；公开仓库只有代码和播放器

· **转写**：本地 Whisper，首章耗时跟音频长度走，缓存好后改对齐逻辑不必重转

· **命令**：素材放进约定目录，按书目和章号跑导入脚本，本机起服务打开网页端

· **验收**：章级校验脚本核对句清单行数和文本分句数；对不上的标插值，不静默丢句

· **外网**：需要时可反代某一章试读，用来验对齐；不是发资源站

> 对齐时容易卡住的地方

书里的拼写和朗读者嘴里说的，经常不是一回事。文本写 mail，音频念 post，这种对不齐时，界面里那行会变半透明，意思是「这句别太较真」。

第一章和后面几章开头也不一样：有的音频前面多念了全书说明，有的多念了章名，得从正文第一句重新找起点，不然后面整段都会偏。

音频文件要放在服务能读到的目录里。指到下载文件夹的快捷方式、搬走的文件，页面上能点开，播起来却是空的——多半是路径问题，不是播放器坏了。

> 适合谁

手头已有电子书文本和配套朗读音频，想自己搭一句级同步，也愿意在本机跑 Whisper 和对齐脚本的开发者。

> 不适合谁

只想打开 App 就听、不想碰导入和部署的读者。完整音频请走正版听书平台；HarryPutter 这边是工程笔记，不是资源站。

你若也在做朗读和文本对句，卡在拼写差异或章首片头，可以把失败样例留在评论区，便于补进 HarryPutter 文档。"""
