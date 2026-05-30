#!/usr/bin/env python3
"""持仓行情查询脚本 - 从持仓执行卡读取股票列表，动态查询实时行情"""
import urllib.request, re, os, sys

DEFAULT_HOLDINGS = os.path.expanduser("~/.qclaw/workspace/持仓执行卡.md")
AGENT_HOLDINGS = os.path.expanduser(
    "~/dev/yolo/tools-workspace/stock-ai/investment-agent/持仓执行卡.md"
)


def _resolve_holdings_file() -> str:
    if "HOLDINGS_CARD" in os.environ and os.environ["HOLDINGS_CARD"]:
        return os.environ["HOLDINGS_CARD"]
    if os.path.exists(DEFAULT_HOLDINGS):
        return DEFAULT_HOLDINGS
    if os.path.exists(AGENT_HOLDINGS):
        return AGENT_HOLDINGS
    return DEFAULT_HOLDINGS


HOLDINGS_FILE = _resolve_holdings_file()

def parse_holdings(filepath):
    """从持仓执行卡解析股票代码和名称"""
    stocks = {}
    if not os.path.exists(filepath):
        print(f"错误: 持仓执行卡不存在 {filepath}")
        return stocks
    with open(filepath, 'r') as f:
        for line in f:
            # 匹配 | 股票 | 代码 | 格式
            m = re.match(r'\|\s*([^|]+?)\s*\|\s*(\d{6})\s*\|', line)
            if m:
                name = m.group(1).strip()
                code = m.group(2).strip()
                # 判断市场：6开头=沪市sh，0/3开头=深市sz
                prefix = 'sh' if code.startswith('6') else 'sz'
                stocks[f'{prefix}{code}'] = name
    return stocks

def get_quotes(stocks):
    """查询实时行情"""
    if not stocks:
        print("无持仓数据")
        return
    codes = ','.join(stocks.keys())
    url = f'https://qt.gtimg.cn/q={codes}'
    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0',
            'Referer': 'https://finance.qq.com'
        })
        content = urllib.request.urlopen(req, timeout=10).read().decode('gbk')
        results = []
        for code, name in stocks.items():
            match = re.search(r'v_' + re.escape(code) + r'="([^"]*)"', content)
            if match:
                parts = match.group(1).split('~')
                if len(parts) > 32:
                    price = parts[3]
                    change_pct = parts[32]
                    change_amt = parts[31]
                    results.append(f"{name}({code[2:]}): {price}元 {change_amt}({change_pct}%)")
            else:
                results.append(f"{name}({code[2:]}): 获取失败")
        for r in results:
            print(r)
    except Exception as e:
        print(f"行情查询失败: {e}")

if __name__ == '__main__':
    stocks = parse_holdings(HOLDINGS_FILE)
    print(f"持仓股票 {len(stocks)} 只:")
    get_quotes(stocks)
