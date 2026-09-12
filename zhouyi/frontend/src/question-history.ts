import type { Question } from "./types";

interface HistoryItem {
  id: string;
  question: Question;
  created_at: string;
}

function normalizeQuestion(value: string) {
  return value.trim().toLocaleLowerCase("zh-CN").replace(/[\s？?！!，,。．]/g, "");
}

export function findRecentMatching(
  question: string,
  items: HistoryItem[],
  now = new Date(),
) {
  const normalized = normalizeQuestion(question);
  if (!normalized) return undefined;
  const cutoff = now.getTime() - 30 * 24 * 60 * 60 * 1000;
  return items.find(
    (item) =>
      new Date(item.created_at).getTime() >= cutoff &&
      normalizeQuestion(item.question.question) === normalized,
  );
}
