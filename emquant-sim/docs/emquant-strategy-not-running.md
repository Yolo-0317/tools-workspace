# 东财量化：SDK 已装但策略「未运行」

> 完整运维见 [PLAYBOOK.md](PLAYBOOK.md)。

SDK 显示已安装 ≠ 策略在跑。策略状态由 **量化终端** 拉起进程；须手动点 **运行** 且配置正确。

## 必做 checklist（仿真）

1. **经典版左下角「量化」** 打开终端，左上角切 **「仿真」**（不是实盘）。
2. **账户管理**：仿真户 `a159f80a-...` 存在且有余额。
3. **量化研究 → 我的策略**：
   - 已有 Python 策略；
   - **设置** 里 **Python 解释器** = `C:\Program Files\Python312-x64\python.exe`（ARM 路径装不了 gm）；
   - **策略 ID** 与 `.env.emquant` 里 `EMQUANT_STRATEGY_ID` 一致。
4. 点策略卡片 **「交易」** 或 **「运行」** → 弹窗里 **关联资金账户** 选仿真户 → 确定。
5. 再点 **「运行」**（或策略监控里启动），状态应变 **运行中**；下方 **Python 控制台** 应有 `=== probe init ===` 等输出。
6. 若仍「未运行」：看控制台 **红色报错**（Token 错、文件名与 `run(filename=)` 不一致、未关联账户等）。

## 常见原因

| 现象 | 处理 |
|------|------|
| 只装了 SDK，没点运行 | 必须点 **运行** |
| 解释器指向 ARM Python | 改为 **Python312-x64** |
| 状态是「研究」 | 切到 **交易/运行**，或从交易入口关联账户后再运行 |
| `filename` 与磁盘文件名不一致 | `run(filename="emquant_probe_main.py")` 须与实际文件名一致 |
| Token 与终端不一致 | 系统设置里复制 Token，更新 `.env.emquant` |
| 终端未登录 / 仿真未连上 | 重登仿真，看状态栏连接是否绿色 |
| 策略秒退 | 看控制台 Traceback；先在策略目录用 x64 python 执行 `main.py` 试 import |
| `on_bar` 报 `bar.get` 不可调用 | 掘金 bar 用 `bar['symbol']`，勿用 `bar.get()`（见 `main.py` 的 `_bar_get`） |

## 本地脚本试跑（Win11 cmd）

```cmd
cd 你的策略目录
set EMQUANT_TOKEN=你的token
"C:\Program Files\Python312-x64\python.exe" -c "from gm.api import *; set_token('%EMQUANT_TOKEN%'); print('gm ok')"
```

模板脚本：`emquant-sim/scripts/win/emquant_probe_main.py`（复制到策略目录并改 strategy_id/token 仅用于命令行调试；**终端内运行勿在代码里写死 token**）。
