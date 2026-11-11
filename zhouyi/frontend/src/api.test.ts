import { afterEach, expect, it, vi } from "vitest";
import { api } from "./api";
afterEach(() => vi.unstubAllGlobals());
it("summarizes 422 field validation in Chinese without exposing Pydantic English", async () => {
  vi.stubGlobal(
    "fetch",
    async () =>
      new Response(
        JSON.stringify({
          detail: [
            {
              type: "string_too_long",
              loc: ["body", "question"],
              msg: "String should have at most 1000 characters",
              ctx: { max_length: 1000 },
            },
            { type: "missing", loc: ["body", "text"], msg: "Field required" },
            {
              type: "unexpected",
              loc: ["body", "unknown"],
              msg: "Input should be valid",
            },
          ],
        }),
        { status: 422 },
      ),
  );
  await expect(api("/readings", {})).rejects.toThrow(
    "问题不能超过 1000 字；请填写笔记；输入内容格式不正确，请检查后重试。",
  );
});
