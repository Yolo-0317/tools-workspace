# A 股个股诊断 QClaw 共享版

这是一个自包含的 QClaw/OpenClaw Skill。它按需获取公开行情，自动判断盘前、盘中、午间、盘后或非交易日，并支持可选的手工持仓指导。

## 环境

- Python 3.10 或更高版本
- 可访问东财公开行情域名
- 不需要 MySQL、Tushare、OpenCLI、`.env` 或第三方 Python 包

检查版本：

```bash
python3 --version
```

## 安装

macOS 或 Linux：

```bash
mkdir -p ~/.openclaw/workspace/skills
cp -R a-share-stock-diagnosis ~/.openclaw/workspace/skills/
```

Windows PowerShell：

```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.openclaw\workspace\skills"
Copy-Item -Recurse a-share-stock-diagnosis "$env:USERPROFILE\.openclaw\workspace\skills\"
```

QClaw 会从其 OpenClaw 工作区加载 Skill，不需要修改 `openclaw.json` 或重启服务。可使用 QClaw 自带的 `qclaw-openclaw` wrapper 执行 `skills list` 和 `skills check` 查看状态。

## 命令测试

```bash
python3 scripts/diagnose.py --symbol 603011 --output json

python3 scripts/diagnose.py --symbol 603011 \
  --shares 300 --cost-price 12.34 --available-shares 300 --output json
```

标准输出始终只有一个 JSON 对象。结果中的 `actionable` 固定为 `false`，不会自动提交交易。

## 数据与缓存

实时行情不落盘。证券映射和已完成日线可以缓存到：

- macOS/Linux：`~/.cache/a-share-stock-diagnosis/`
- Windows：`%LOCALAPPDATA%\a-share-stock-diagnosis\`

持仓参数、诊断结果和对话不会写入缓存。当前版本内置经核对的 2026 年 SSE 交易日历；超出覆盖年份时严格返回“交易日历未知”，不会把普通工作日猜成交易日。

## 自检

在 Skill 目录执行：

```bash
python3 -m unittest discover -s tests -v
python3 -m compileall -q a_share_stock_diagnosis scripts tests
```

## 故障排查

- `Python 版本过低`：安装 Python 3.10 或更高版本。
- `公开行情接口暂时不可用`：检查网络后重试，禁止凭空补行情。
- `股票名称对应多个候选`：改用六位股票代码。
- `交易日历未覆盖当前日期`：更新到包含该年份日历的新版本。

## 卸载

只删除安装的 `a-share-stock-diagnosis` Skill 文件夹。公开行情缓存可单独删除，不影响其他 QClaw 数据。
