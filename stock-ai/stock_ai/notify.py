"""飞书 / Lark 通知。"""

import json
import time

import requests

from stock_ai.logging import get_logger

logger = get_logger("monitor")

FEISHU_BOT_URL = (
    "https://open.feishu.cn/open-apis/bot/v2/hook/6ae3c4bc-a50e-49dc-b75d-fa9a217b2299"
)
LARK_MSG_TIMEOUT = 3
NOTIFY_MSG_ENV_PREFIX = "【简单的提醒】"


def send_to_lark(
    message: str, is_error: bool = False, max_retries: int = 3, retry_delay: int = 2
) -> bool:
    formatted_message = f"{NOTIFY_MSG_ENV_PREFIX}\n{message}"
    retry_count = max_retries if not is_error else 0

    for attempt in range(retry_count + 1):
        try:
            response = requests.post(
                url=FEISHU_BOT_URL,
                data=json.dumps(
                    {"msg_type": "text", "content": {"text": formatted_message}}
                ),
                headers={"Content-Type": "application/json"},
                proxies={"http": "", "https": ""},
                timeout=LARK_MSG_TIMEOUT,
            )
            response_obj = response.json()
            if response.status_code == 200 and response_obj.get("StatusCode") == 0:
                return True
            logger.warning(f"飞书通知发送失败，状态码: {response.text}")
        except Exception as e:
            logger.error(f"飞书通知发送异常: {e}")

        if attempt < retry_count:
            logger.info(f"等待 {retry_delay} 秒后重试，(第{attempt + 1}次尝试)")
            time.sleep(retry_delay)

    if not is_error:
        send_to_lark(f"{message}重试失败", is_error=True)
    else:
        logger.error("【失败消息】飞书通知发送失败，错误消息不重试")
    return False
