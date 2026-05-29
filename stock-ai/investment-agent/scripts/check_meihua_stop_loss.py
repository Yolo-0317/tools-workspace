#!/usr/bin/env python3
"""
梅花生物止损监控脚本
触发条件：sh600873 跌破 9.00 元
"""
import urllib.request
import re
import sys

STOP_LOSS_PRICE = 9.00

try:
    url = "https://qt.gtimg.cn/q=sh600873"
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0',
        'Referer': 'https://finance.qq.com'
    })
    content = urllib.request.urlopen(req, timeout=8).read().decode('gbk')
    match = re.search(r'v_sh600873="([^"]+)"', content)
    if match:
        parts = match.group(1).split('~')
        price = float(parts[3])
        pct = parts[31]
        name = parts[1]

        if price < STOP_LOSS_PRICE:
            msg = (
                f"🚨【止损警报】{name}(600873)\n"
                f"现价 {price} 元，跌破止损价 {STOP_LOSS_PRICE} 元！\n"
                f"请立即执行清仓操作！"
            )
        else:
            msg = None  # 价格正常，不发送消息

        print(f"PRICE:{price}:{pct}")
        if msg:
            print(f"ALERT:{msg}")
        else:
            print(f"NORMAL:现价{price}元，止损价{STOP_LOSS_PRICE}元，暂未触发止损")
    else:
        print("NORMAL:数据解析失败，跳过")
except Exception as e:
    print(f"NORMAL:获取失败({e})，跳过")
