#!/usr/bin/env python3
"""公众号「工作区技术分享」稿：系列总览（静态成稿）。"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from scripts._bootstrap import ensure_repo_root_on_path

ensure_repo_root_on_path()

TZ = ZoneInfo("Asia/Shanghai")

# 公众号对外项目名（不用 git 目录名 tools-workspace）
PROJECT_NAME = "工具工作区"
SERIES_TAG = f"{PROJECT_NAME} · 技术分享"


def workspace_overview_title(*, now: datetime | None = None) -> str:
    from scripts.tools.wechat_mp_content import _pick_clickbait_title

    _ = now or datetime.now(TZ)
    return _pick_clickbait_title(
        [
            "一个仓库里的自动化长什么样？先逛全景",
            "收盘推送和证书续签，原来在同一套 git 里？",
            "从行情入库到公众号草稿：幕后长啥样？",
            "脚本越写越散？后来全收进了一个仓库",
        ]
    )


def workspace_overview_digest() -> str:
    return (
        f"「{PROJECT_NAME}」：收盘入库、微信战报、四条公众号草稿、"
        "证书续签和仿真，一个 git 里怎么分工、一天怎么跑。"
    )[:128]


def generate_workspace_overview_body(*, now: datetime | None = None) -> str:
    """工作区总览：口语化客观叙述；分块标题用 > 引用行（见 text_to_html）。"""
    _ = now or datetime.now(TZ)

    return f"""收盘后大约一刻钟，固定会跑完一串事：日线进 MySQL，综合/五因子/均线回踩各落一张表，战报推微信，宏观、Top5、龙头、技术分享四条草稿各覆写一遍。盘中东财现价轮询，触线就报警；SideStore 证书在过期前续签。这些原先散在六七个地方各自维护，后来收成个人项目「{PROJECT_NAME}」——一个 git 管股票、推送、证书和草稿。下文按模块和一天顺序说明。

> 它是什么

「{PROJECT_NAME}」就是收盘以后要跑的那一套：入库、选股、推送、草稿、证书，外加盘中监控。不是成品软件，是常年堆起来的脚本和容器。Python 和 docker 为主，mac 上几条定时任务，Win11 里另有一台仿真机。股票自动化占大头，旁边是微信、看板、自托管证书；家用影音在仓库外单独跑，登录 Mac 时和其他服务一起起来。

> 里面分几块

股票主仓：收盘写库，选股出综合、五因子、均线回踩等多张表；公众号五条观察名单从多路结果合并后再按分数挑，不是顺手抄某张表前几行。策略纪律和给 Cursor 看的备忘也在这块，改规则有文件可查。

业务数据库：MySQL 表结构和迁移单独维护，和业务代码分开，回滚时少心慌。

微信桥接：战报、监控报警、选股跑完提醒都从这发。另一路微信机器人必须分开登录——曾踩过抢号，现在写进备忘。

自托管与证书：侧载、反向代理、域名和续签；网盘、影音也能从同一网关进，只写合法自托管用途。

仿真机：Win11 虚拟机里跑券商仿真终端，和 Mac 上的实盘脚本不装在一台机器里。

> 和数据打交道

行情以 Tushare 入库为主；Cursor 里挂了 MCP，查均线、翻日线不用另开终端。

盘中监控大约每五分钟用浏览器读东财现价，到了条件就打微信。阈值写在库里，看板能看到今天触了几次。

龙头和 Top5 的公众号稿走快采：页面快照加 K 线，缓存在单独文件夹，和收盘后那套八维度深度 SOP 分开，免得三点钟扎堆把浏览器卡死。

宏观另拉要闻；情绪周期、龙头池各有一张检查表，和选股表不是一回事。

> 公众号草稿

草稿箱固定四个坑位，每次覆盖旧稿，封面也四套：宏观、收盘 Top5、龙头、再加这篇技术分享。前三篇会调模型写稿；技术分享是手写正文，每天不跟着换腔调。

跑 `wechat_mp_draft` 可以四篇一起推，也可以只推某一类。封面从素材库挑竖图，再裁成公众号要的宽高。

> 微信和看板

除了推送，手机里能甩一句「选股跑完没」「查 000725」，Cursor 会去翻库——人不在 Mac 前时靠这个救火。

看板页面只读：选股、情绪、任务有没有失败。网页里不放聊天框。

> 一天大概顺序

登录 Mac，docker 自己起来（Desktop 开了自启，compose 写了 unless-stopped）。白天监控转着；收盘入库、选股、战报；然后更四篇草稿。

改推送或草稿相关代码前，习惯先 pytest，再 `wechat_mp_draft --kind workspace` 只更一篇，免得误伤别的坑位。

> 以后可能写的

全景先到这。若要拆篇，可能写入库细节、微信桥接、证书续签、看板字段、仿真机维护、备忘怎么记——哪块优先看你更关心什么。"""
