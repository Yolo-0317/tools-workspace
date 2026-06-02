#!/bin/sh
# [已废弃] 战报微信推送已移除；快讯 + AI 解读见 sync_macro_news.sh（每 15 分钟 launchd）
echo "⚠️  每日战报微信推送已停用。" >&2
echo "    快讯落库 + Cursor AI 解读: ./sync_macro_news.sh" >&2
echo "    launchd: com.user.stock-macro-news-sync" >&2
exit 1
