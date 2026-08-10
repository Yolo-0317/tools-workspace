# shellcheck shell=bash
# 与本机 ~/.zshrc 中 proxy_on 一致；brew / curl 下载 ghcr bottle 时使用。
PROXY_URL="${PROXY_URL:-http://127.0.0.1:10888}"

export HTTP_PROXY="$PROXY_URL"
export HTTPS_PROXY="$PROXY_URL"
export http_proxy="$PROXY_URL"
export https_proxy="$PROXY_URL"
export ALL_PROXY="$PROXY_URL"
export all_proxy="$PROXY_URL"
export no_proxy="${no_proxy:-localhost,127.0.0.1,::1}"

# 避免 Cursor 沙箱改写缓存目录
export HOMEBREW_CACHE="${HOMEBREW_CACHE:-$HOME/Library/Caches/Homebrew}"
export HOMEBREW_NO_AUTO_UPDATE="${HOMEBREW_NO_AUTO_UPDATE:-1}"
