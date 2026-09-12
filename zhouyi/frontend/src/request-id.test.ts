import { expect, it, vi } from "vitest";
import { requestId } from "./request-id";
it("creates UUID v4 when LAN HTTP lacks randomUUID", () => {
  const cryptoWithoutUUID = {
    getRandomValues: crypto.getRandomValues.bind(crypto),
  };
  vi.stubGlobal("crypto", cryptoWithoutUUID);
  try {
    const a = requestId(),
      b = requestId();
    expect(a).toMatch(
      /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
    );
    expect(a).not.toBe(b);
  } finally {
    vi.unstubAllGlobals();
  }
});
