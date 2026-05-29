# 日线同步定时任务（Docker）

工作日 **17:00（Asia/Shanghai）** 自动执行 `run_sync_daily.sh`，按日期批量拉取最近 **7** 天全市场日线写入 MySQL。

## 前置条件

1. 在 `stock-ai/.env` 中配置：

   ```bash
   TUSHARE_TOKEN=你的token
   MYSQL_URL=mysql+pymysql://用户:密码@主机:3306/库名
   ```

2. **MySQL 在宿主机时**：容器内不能使用 `127.0.0.1`，请将 `MYSQL_URL` 主机改为 `host.docker.internal`（macOS / Docker Desktop 已在本 compose 中配置 `extra_hosts`）。

3. 本机已安装 Docker Compose v2。

## 启动

```bash
cd stock-ai/docker/daily-sync
docker compose up -d --build
```

查看日志：

```bash
docker compose logs -f stock-daily-sync
tail -f ../../logs/sync_daily.log
```

## 手动执行一次

```bash
docker compose run --rm stock-daily-sync ./run_sync_daily.sh
```

## 停止

```bash
docker compose down
```

## 说明

- 调度器：[supercronic](https://github.com/aptible/supercronic)，cron 表达式见 `crontab`（周一～周五 17:00）。
- 非交易日当天 Tushare 无数据时会跳过，属正常情况。
- 修改调度时间：编辑 `crontab` 后 `docker compose up -d --build`。
