import { expect, it } from "vitest";
import { findRecentMatching } from "./question-history";

it("finds the same normalized question from the previous thirty days", () => {
  const items = [
    { id: "old", question: { question: "  如何推进 项目？ ", topic: "", background: "", horizon: "" }, created_at: "2026-09-01T00:00:00Z" },
    { id: "expired", question: { question: "如何推进项目？", topic: "", background: "", horizon: "" }, created_at: "2026-07-01T00:00:00Z" },
  ];

  expect(findRecentMatching("如何推进项目?", items, new Date("2026-09-12T00:00:00Z"))?.id).toBe("old");
  expect(findRecentMatching("另一个问题", items, new Date("2026-09-12T00:00:00Z"))).toBeUndefined();
});
