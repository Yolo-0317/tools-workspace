import { mount, flushPromises } from "@vue/test-utils";
import { it, expect, vi, afterEach } from "vitest";
import { createRouter, createMemoryHistory } from "vue-router";
import ElementPlus from "element-plus";
import HistoryView from "./views/HistoryView.vue";
import ClassicsView from "./views/ClassicsView.vue";
afterEach(() => vi.unstubAllGlobals());
async function setup(component: any) {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component }],
  });
  await router.push("/");
  await router.isReady();
  const w = mount(component, { global: { plugins: [ElementPlus, router] } });
  await flushPromises();
  return w;
}
it("history empty state leads to asking a question", async () => {
  vi.stubGlobal(
    "fetch",
    async () => new Response(JSON.stringify({ items: [], total: 0 })),
  );
  const w = await setup(HistoryView);
  expect(w.text()).toContain("还没有问卦记录");
  expect(w.get("a").attributes("href")).toBe("/");
  w.unmount();
});
it("marks Najia records in history", async () => {
  vi.stubGlobal(
    "fetch",
    async () => new Response(JSON.stringify({
      total: 1,
      items: [{
        id: "n1",
        mode: "najia",
        question: { question: "如何推进项目？", topic: "", background: "", horizon: "" },
        cast: { values: [7, 7, 7, 7, 7, 7], moving: [], original_bits: "111111", changed_bits: "111111", original_id: 1, changed_id: 1 },
        created_at: "2026-09-12T12:00:00Z",
      }],
    })),
  );

  const w = await setup(HistoryView);
  expect(w.get(".history-row").text()).toContain("六爻纳甲");
  w.unmount();
});
it("loads first classic and renders source markup as plain text", async () => {
  const source = {
    id: "s1",
    role: "background",
    book: "周易",
    edition: "通行本",
    chapter: "乾",
    text: "<script>danger</script>元亨利贞",
    source_url: "https://example.com",
    checksum: "sha",
    verification: "checked",
    hexagram_id: 1,
    kind: "judgment",
    position: null,
  };
  vi.stubGlobal(
    "fetch",
    async (url: string) =>
      new Response(
        JSON.stringify(
          url === "/api/classics"
            ? [{ id: 1, name: "乾", bits: "111111" }]
            : {
                id: 1,
                name: "乾",
                bits: "111111",
                judgment: source,
                lines: [],
                use: null,
                tuan: source,
                xiang: source,
                xiaoxiang: [],
                commentaries: [],
              },
        ),
      ),
  );
  const w = await setup(ClassicsView);
  expect(w.text()).toContain("<script>danger</script>元亨利贞");
  expect(w.find("script").exists()).toBe(false);
  w.unmount();
});
it.each(["success", "failure"])(
  "keeps page three when the older page two request finishes with %s",
  async (outcome) => {
    const pending = new Map<string, (response: Response) => void>();
    const item = (id: string) => ({
      id,
      question: { question: id, topic: "", background: "", horizon: "" },
      cast: {
        coins: [],
        values: [7, 7, 7, 7, 7, 7],
        moving: [],
        original_bits: "111111",
        changed_bits: "111111",
        original_id: 1,
        changed_id: 1,
      },
      created_at: "2026-09-12T12:00:00Z",
    });
    vi.stubGlobal("fetch", async (url: string) =>
      url.includes("offset=0")
        ? new Response(JSON.stringify({ items: [item("第一页")], total: 60 }))
        : new Promise<Response>((resolve) => pending.set(url, resolve)),
    );
    const w = await setup(HistoryView);
    await w
      .findAll(".el-pager li")
      .find((li) => li.text() === "2")!
      .trigger("click");
    await flushPromises();
    await w
      .findAll(".el-pager li")
      .find((li) => li.text() === "3")!
      .trigger("click");
    await flushPromises();
    pending.get("/api/readings?offset=40&limit=20")!(
      new Response(JSON.stringify({ items: [item("第三页")], total: 60 })),
    );
    await flushPromises();
    expect(w.get(".history-row").text()).toContain("第三页");
    pending.get("/api/readings?offset=20&limit=20")!(
      outcome === "success"
        ? new Response(JSON.stringify({ items: [item("第二页")], total: 60 }))
        : new Response(JSON.stringify({ detail: "旧请求失败" }), {
            status: 500,
          }),
    );
    await flushPromises();
    expect(w.get(".history-row").text()).toContain("第三页");
    expect(w.text()).not.toContain("旧请求失败");
    expect(w.get(".el-pager .is-active").text()).toBe("3");
    w.unmount();
  },
);
