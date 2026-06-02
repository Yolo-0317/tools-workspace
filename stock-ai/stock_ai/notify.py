"""飞书 / Lark 通知。"""

from __future__ import annotations

import json
import os
import time

import requests

from stock_ai.logging import get_logger

logger = get_logger("monitor")

_DEFAULT_FEISHU_BOT_URL = (
    "https://open.feishu.cn/open-apis/bot/v2/hook/6ae3c4bc-a50e-49dc-b75d-fa9a217b2299"
)
LARK_MSG_TIMEOUT = 3
NOTIFY_MSG_ENV_PREFIX = "【简单的提醒】"


def feishu_bot_url() -> str:
    return (os.environ.get("FEISHU_BOT_URL") or _DEFAULT_FEISHU_BOT_URL).strip()


def send_to_lark(
    message: str,
    is_error: bool = False,
    max_retries: int = 3,
    retry_delay: int = 2,
    *,
    prefix: str | None = None,
) -> bool:
    url = feishu_bot_url()
    if not url:
        logger.error("未配置 FEISHU_BOT_URL，跳过飞书通知")
        return False

    head = prefix if prefix is not None else NOTIFY_MSG_ENV_PREFIX
    formatted_message = f"{head}\n{message}" if head else message
    retry_count = max_retries if not is_error else 0

    for attempt in range(retry_count + 1):
        try:
            response = requests.post(
                url=url,
                data=json.dumps(
                    {"msg_type": "text", "content": {"text": formatted_message}}
                ),
                headers={"Content-Type": "application/json"},
                proxies={"http": "", "https": ""},
                timeout=LARK_MSG_TIMEOUT,
            )
            response_obj = response.json()
            ok = response.status_code == 200 and (
                response_obj.get("StatusCode") == 0 or response_obj.get("code") == 0
            )
            if ok:
                return True
            logger.warning(f"飞书通知发送失败，状态码: {response.text}")
        except Exception as e:
            logger.error(f"飞书通知发送异常: {e}")

        if attempt < retry_count:
            logger.info(f"等待 {retry_delay} 秒后重试，(第{attempt + 1}次尝试)")
            time.sleep(retry_delay)

    if not is_error:
        send_to_lark(f"{message}重试失败", is_error=True, prefix=prefix)
    else:
        logger.error("【失败消息】飞书通知发送失败，错误消息不重试")
    return False
