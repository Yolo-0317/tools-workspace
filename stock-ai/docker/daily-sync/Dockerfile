# Tushare 日线 → MySQL，工作日 17:00 由 supercronic 触发
FROM python:3.12-slim-bookworm

ARG SUPERCRONIC_VERSION=0.2.33
# TARGETARCH 由 Docker BuildKit 注入（amd64 / arm64）

RUN apt-get update \
  && apt-get install -y --no-install-recommends curl ca-certificates tzdata \
  && case "${TARGETARCH:-$(uname -m)}" in \
       amd64|x86_64) sc_arch=amd64 ;; \
       arm64|aarch64) sc_arch=arm64 ;; \
       *) echo "unsupported arch: ${TARGETARCH:-$(uname -m)}" >&2; exit 1 ;; \
     esac \
  && curl -fsSL "https://github.com/aptible/supercronic/releases/download/v${SUPERCRONIC_VERSION}/supercronic-linux-${sc_arch}" \
    -o /usr/local/bin/supercronic \
  && chmod +x /usr/local/bin/supercronic \
  && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
COPY stock_ai ./stock_ai
COPY scripts ./scripts

COPY run_sync_daily.sh ./
COPY docker/daily-sync/crontab /etc/cron.d/stock-daily-sync
COPY docker/daily-sync/entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh run_sync_daily.sh \
  && uv sync --frozen --no-dev

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
