# shellcheck shell=bash
load_aliyun_env() {
  local sidestore_home="${SIDESTORE_HOME:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

  if [[ -n "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" && -n "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
    return 0
  fi

  if [[ -f "$sidestore_home/.env.secrets" ]]; then
    set -a
    # shellcheck disable=SC1091
    source "$sidestore_home/.env.secrets"
    set +a
    if [[ -n "${ALIBABA_CLOUD_ACCESS_KEY_ID:-}" && -n "${ALIBABA_CLOUD_ACCESS_KEY_SECRET:-}" ]]; then
      return 0
    fi
  fi

  # launchd 下 bash 不能直接 source .zshrc（oh-my-zsh 会报错）
  if command -v zsh >/dev/null 2>&1; then
    local key_id key_secret
    key_id="$(zsh -lic 'printf %s "$ALIBABA_CLOUD_ACCESS_KEY_ID"' 2>/dev/null || true)"
    key_secret="$(zsh -lic 'printf %s "$ALIBABA_CLOUD_ACCESS_KEY_SECRET"' 2>/dev/null || true)"
    if [[ -n "$key_id" && -n "$key_secret" ]]; then
      export ALIBABA_CLOUD_ACCESS_KEY_ID="$key_id"
      export ALIBABA_CLOUD_ACCESS_KEY_SECRET="$key_secret"
      umask 077
      printf 'ALIBABA_CLOUD_ACCESS_KEY_ID=%q\nALIBABA_CLOUD_ACCESS_KEY_SECRET=%q\n' \
        "$key_id" "$key_secret" >"$sidestore_home/.env.secrets"
      return 0
    fi
  fi

  return 1
}
