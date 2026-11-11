#!/usr/bin/env python3

import re
import sys
from pathlib import Path


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


if len(sys.argv) != 2:
    fail("usage: validate_late_pose_prompt.py <prompt-file>")

prompt_path = Path(sys.argv[1])
if not prompt_path.is_file():
    fail(f"prompt file does not exist: {prompt_path}")

text = prompt_path.read_text(encoding="utf-8")

required_patterns = {
    "one-second dance start": r"1(?:\.0{1,3})?\s*秒内.{0,40}(?:主体舞段|主体移动|主体路线|旋转准备)",
    "active movement through 9.7 seconds": r"9\.7(?:0{1,2})?\s*秒前.{0,80}(?:脚步|重心|躯干|上肢|主动作)",
    "continuous ending mode": r"(?:不进入定式|不做定式|无定式)",
    "movement on the last frame": r"最后一帧.{0,30}(?:有效舞动|仍在舞动|运动中).{0,20}(?:结束|切断)",
}

for label, pattern in required_patterns.items():
    if re.search(pattern, text, flags=re.DOTALL) is None:
        fail(f"missing {label}: {prompt_path}")

early_pose = re.search(
    r"(?:[0-8](?:\.\d+)?|9\.[0-6]\d*)\s*秒.{0,30}(?:完成|进入|形成).{0,12}(?:定式|定格|站定)",
    text,
    flags=re.DOTALL,
)
if early_pose is not None:
    fail(f"pose finishes before 9.7 seconds: {early_pose.group(0)!r}")

print(f"PASS: {prompt_path}")
