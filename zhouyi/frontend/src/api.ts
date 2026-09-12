import type { ClassicSummary } from "./types";
export async function api<T>(path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(
      `/api${path}`,
      body === undefined
        ? undefined
        : {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(body),
          },
    );
  } catch {
    throw new Error("暂时无法连接服务，请检查网络后重试。");
  }
  if (!response.ok) {
    let detail: unknown;
    try {
      detail = (await response.json()).detail;
    } catch {}
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? [...new Set(detail.map(validationMessage))].join("；")
          : `请求未完成（${response.status}），请稍后重试。`,
    );
  }
  return response.json();
}
let classics: Promise<ClassicSummary[]> | undefined;
export function listHexagrams() {
  return (classics ??= api<ClassicSummary[]>("/classics").catch((e) => {
    classics = undefined;
    throw e;
  }));
}
export function date(value: string) {
  return new Date(value).toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}
export function errorText(e: unknown) {
  return e instanceof Error ? e.message : "操作未完成，请重试。";
}

function validationMessage(issue: {
  type?: string;
  loc?: unknown[];
  ctx?: { max_length?: number; min_length?: number };
}): string {
  const labels: Record<string, string> = {
    question: "问题",
    background: "背景",
    horizon: "关注时间",
    text: "笔记",
    topic: "方向",
    request_id: "请求编号",
  };
  const field = labels[String(issue.loc?.at(-1))];
  if (!field) return "输入内容格式不正确，请检查后重试。";
  if (
    issue.type === "string_too_long" &&
    typeof issue.ctx?.max_length === "number"
  )
    return `${field}不能超过 ${issue.ctx.max_length} 字`;
  if (issue.type === "missing" || issue.type === "string_too_short")
    return `请填写${field}`;
  return `${field}格式不正确，请检查后重试。`;
}
