/** 上海时区 YYYY-MM-DD（与 stock-ai 监控状态文件日期对齐） */
export function shanghaiToday(): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: 'Asia/Shanghai',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(new Date())
}
