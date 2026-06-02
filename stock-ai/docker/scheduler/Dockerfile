# stock-ai 统一调度：Tushare sync（容器）+ 选股/战报/监控（触发本机 host-jobs）
FROM python:3.12-slim-bookworm

ARG SUPERCRONIC_VERSION=0.2.33

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
COPY docker ./docker

COPY run_sync_daily.sh sync_emotion_cycle.sh ./

COPY docker/scheduler/crontab /etc/cron.d/stock-ai-scheduler
COPY docker/scheduler/entrypoint.sh /entrypoint.sh
COPY docker/scheduler/run-host-job.sh ./docker/scheduler/run-host-job.sh

RUN chmod +x /entrypoint.sh run_sync_daily.sh sync_emotion_cycle.sh docker/scheduler/run-host-job.sh \
  && uv sync --frozen --no-dev

ENV TZ=Asia/Shanghai
ENV PYTHONUNBUFFERED=1

ENTRYPOINT ["/entrypoint.sh"]
