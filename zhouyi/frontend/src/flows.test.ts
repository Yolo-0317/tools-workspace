import { mount, flushPromises } from "@vue/test-utils";
import { beforeEach, afterEach, expect, it, vi } from "vitest";
import ElementPlus from "element-plus";
import { createRouter, createMemoryHistory } from "vue-router";
import CastView from "./views/CastView.vue";
import ReadingView from "./views/ReadingView.vue";
import Hexagram from "./components/Hexagram.vue";
const reading = {
  id: "r-1",
  request_id: "q-1",
  question: {
    question: "如何安排学习？",
    topic: "study",
    background: "",
    horizon: "",
  },
  cast: {
    coins: [
      [2, 2, 3],
      [2, 3, 3],
      [2, 2, 3],
      [2, 3, 3],
      [2, 2, 3],
      [2, 3, 3],
    ],
    values: [7, 8, 7, 8, 7, 8],
    moving: [],
    original_bits: "101010",
    changed_bits: "101010",
    original_id: 1,
    changed_id: 1,
  },
  selection: { version: "v1", reason: "无变爻", primary: [], secondary: [] },
  materials: [],
  created_at: "2026-09-12T12:00:00Z",
  interpretations: [],
  reflections: [],
  mode: "classic",
  calendar: null,
  najia: null,
};
let requests: { url: string; body: any }[] = [];
let resolveCast: (v: any) => void;
let responseReading: any;
beforeEach(() => {
  sessionStorage.clear();
  requests = [];
  responseReading = structuredClone(reading);
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      requests.push({
        url,
        body: init?.body ? JSON.parse(String(init.body)) : null,
      });
      if (url === "/api/topics")
        return new Response(
          JSON.stringify([
            { id: "study", label: "学习", templates: ["如何安排学习？"] },
          ]),
        );
      if (url === "/api/classics")
        return new Response(
          JSON.stringify([{ id: 1, name: "乾", bits: "111111" }]),
        );
      if (url === "/api/readings" && init?.method === "POST")
        return new Promise((r) => {
          resolveCast = (v) => r(new Response(JSON.stringify(v)));
        });
      if (url.endsWith("/interpretations"))
        return new Response(
          JSON.stringify({
            id: "a-new",
            status: "running",
            model: "test",
            prompt_version: "v1",
            started_at: new Date().toISOString(),
            finished_at: null,
            result: null,
            error: null,
          }),
        );
      return new Response(JSON.stringify(responseReading));
    }),
  );
});
afterEach(() => vi.unstubAllGlobals());
async function setup(component: any, path = "/") {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: "/:pathMatch(.*)*", component }],
  });
  await router.push(path);
  await router.isReady();
  const wrapper = mount(component, {
    global: { plugins: [ElementPlus, router] },
  });
  await flushPromises();
  return wrapper;
}
it("topic template stays editable and one in-flight click submits only once", async () => {
  const w = await setup(CastView);
  await w.get('[data-testid="template"]').trigger("click");
  const input = w.get("textarea");
  expect((input.element as HTMLTextAreaElement).value).toBe("如何安排学习？");
  await input.setValue("未来三个月如何安排学习？");
  await w.get('[data-testid="cast"]').trigger("click");
  await w.get('[data-testid="cast"]').trigger("click");
  expect(requests.filter((r) => r.url === "/api/readings")).toHaveLength(1);
  expect(requests.find((r) => r.url === "/api/readings")?.body.question).toBe(
    "未来三个月如何安排学习？",
  );
  resolveCast(reading);
  await flushPromises();
  w.unmount();
});

it("sends Beijing time and location only when Najia mode is selected", async () => {
  const w = await setup(CastView);
  await w.get('[data-testid="najia-mode"]').trigger("click");
  await w.get("textarea").setValue("这项工作该如何推进？");
  await w.get('[data-testid="cast-location"]').setValue("杭州");
  await w.get('[data-testid="cast"]').trigger("click");

  const body = requests.find((request) => request.url === "/api/readings")?.body;
  expect(body.mode).toBe("najia");
  expect(body.location).toBe("杭州");
  expect(body.cast_time).toMatch(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:00\+08:00$/);
  resolveCast({ ...reading, mode: "najia" });
  await flushPromises();
  expect(w.findComponent({ name: "CyberCast" }).exists()).toBe(true);
  await w.get('[data-testid="skip-cast-animation"]').trigger("click");
  w.unmount();
});

it("shows the saved Najia chart separately from the classic passages", async () => {
  responseReading = {
    ...structuredClone(reading),
    mode: "najia",
    question: { ...reading.question, location: "杭州", cast_time: "2024-02-10T10:00:00+08:00" },
    calendar: {
      beijing_time: "2024-02-10T10:00:00+08:00",
      year_ganzhi: "甲辰",
      month_ganzhi: "丙寅",
      day_ganzhi: "甲辰",
      hour_ganzhi: "己巳",
      xunkong: ["寅", "卯"],
      version: "beijing-midnight-v1",
    },
    najia: {
      version: "jingfang-najia-v1",
      palace: "乾",
      palace_element: "金",
      palace_stage: "本宫",
      shi_position: 6,
      ying_position: 3,
      use_candidates: ["官鬼"],
      sources: [{
        book: "增删卜易",
        chapters: ["八纯卦纳甲图", "世应章第六"],
        source_url: "https://example.com/najia",
        verification: "来源抽取并核对规则表，尚未逐字校勘",
      }],
      original_lines: [1, 2, 3, 4, 5, 6].map((position) => ({
        position,
        yin_yang: position % 2 ? "阳" : "阴",
        stem_branch: "甲子",
        element: "水",
        relative: "子孙",
        spirit: "青龙",
        moving: false,
        flags: [],
        influences: ["月生", "日克"],
      })),
      changed_lines: [],
      observations: [],
    },
  };

  const w = await setup(ReadingView, "/readings/r-1");
  expect(w.text()).toContain("六爻纳甲排盘");
  expect(w.text()).toContain("甲辰年 · 丙寅月 · 甲辰日 · 己巳时");
  expect(w.text()).toContain("北京时间零点换日");
  expect(w.findAll('[data-testid="najia-line"]')).toHaveLength(6);
  expect(w.find('[data-testid="najia-use"]').exists()).toBe(true);
  expect(requests.some((request) => request.url.endsWith("/interpretations"))).toBe(false);
  expect(w.find('[data-testid="start-najia-interpretation"]').exists()).toBe(true);
  expect(w.get('[data-testid="najia-source"]').attributes("href")).toBe("https://example.com/najia");
  w.unmount();
});
it("reloads stored reading without posting a new cast; failed interpretation retries same reading", async () => {
  responseReading.interpretations = [
    {
      id: "a-old",
      status: "failed",
      model: "test",
      prompt_version: "v1",
      started_at: "2026-09-12T12:00:00Z",
      finished_at: "2026-09-12T12:01:00Z",
      result: null,
      error: "网络失败",
    },
  ];
  const w = await setup(ReadingView, "/readings/r-1");
  expect(w.text()).toContain("如何安排学习？");
  expect(requests.some((r) => r.url === "/api/readings")).toBe(false);
  await w.get('[data-testid="retry-interpretation"]').trigger("click");
  await flushPromises();
  expect(
    requests.filter((r) => r.url === "/api/readings/r-1/interpretations"),
  ).toHaveLength(1);
  expect(w.text()).toContain("正在解读");
  w.unmount();
});
it("shows sixth line at top and first moving line at bottom", () => {
  const w = mount(Hexagram, { props: { bits: "100000", moving: [1] } });
  const rows = w.findAll("[data-position]");
  expect(rows[0].attributes("data-position")).toBe("6");
  expect(rows[0].classes()).toContain("yin");
  expect(rows[5].classes()).toContain("yang");
  expect(rows[5].classes()).toContain("moving");
});
it("preserves question and request ID after network failure, and changes ID after editing", async () => {
  const baseFetch = fetch;
  let casts: any[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    if (url === "/api/readings" && init?.method === "POST") {
      casts.push(JSON.parse(String(init.body)));
      throw new Error("offline");
    }
    return baseFetch(url, init);
  });
  const w = await setup(CastView);
  await w.get("textarea").setValue("如何安排学习？");
  await w.get('[data-testid="cast"]').trigger("click");
  await flushPromises();
  expect(w.text()).toContain("暂时无法连接服务");
  expect((w.get("textarea").element as HTMLTextAreaElement).value).toBe(
    "如何安排学习？",
  );
  await w.get('[data-testid="cast"]').trigger("click");
  await flushPromises();
  expect(casts[1].request_id).toBe(casts[0].request_id);
  await w.get("textarea").setValue("如何安排明年的学习？");
  await w.get('[data-testid="cast"]').trigger("click");
  await flushPromises();
  expect(casts[2].request_id).not.toBe(casts[0].request_id);
  w.unmount();
});
it("polls a running interpretation and stops after unmount", async () => {
  vi.useFakeTimers();
  try {
    responseReading.interpretations = [
      {
        id: "a-run",
        status: "running",
        model: "test",
        prompt_version: "v1",
        started_at: new Date().toISOString(),
        finished_at: null,
        result: null,
        error: null,
      },
    ];
    const w = await setup(ReadingView, "/readings/r-1");
    await vi.advanceTimersByTimeAsync(2000);
    await flushPromises();
    expect(requests.filter((r) => r.url === "/api/readings/r-1")).toHaveLength(
      2,
    );
    w.unmount();
    await vi.advanceTimersByTimeAsync(6000);
    expect(requests.filter((r) => r.url === "/api/readings/r-1")).toHaveLength(
      2,
    );
  } finally {
    vi.useRealTimers();
  }
});
it.each([
  ["textarea", 1001, "问题不能超过 1000 字"],
  ['input[placeholder="补充关键处境"]', 3001, "背景不能超过 3000 字"],
  ['input[placeholder="例如：未来三个月"]', 101, "关注时间不能超过 100 字"],
])(
  "rejects oversized field %s before posting",
  async (selector, length, message) => {
    const w = await setup(CastView);
    await w.get("textarea").setValue("如何安排学习？");
    await w.get(selector).setValue("字".repeat(length));
    await w.get('[data-testid="cast"]').trigger("click");
    await flushPromises();
    expect(requests.some((r) => r.url === "/api/readings")).toBe(false);
    expect(w.text()).toContain(message);
    w.unmount();
  },
);
it("rejects reflection longer than 5000 characters before saving", async () => {
  const w = await setup(ReadingView, "/readings/r-1");
  await w.get('textarea[aria-label="回看笔记"]').setValue("字".repeat(5001));
  await w.get(".reflection-button").trigger("click");
  await flushPromises();
  expect(requests.some((r) => r.url.endsWith("/reflections"))).toBe(false);
  expect(w.text()).toContain("笔记不能超过 5000 字");
  w.unmount();
});
it("citation has one target, opens its collapsed sources and version, then focuses it", async () => {
  responseReading.materials = [
    {
      id: "s-1",
      role: "primary",
      book: "周易",
      edition: "通行本",
      chapter: "乾",
      text: "元亨利贞",
      source_url: "https://example.com",
      checksum: "sha",
      verification: "checked",
      hexagram_id: 1,
      kind: "judgment",
      position: null,
    },
  ];
  responseReading.interpretations = [
    {
      id: "a-ok",
      status: "succeeded",
      model: "test",
      prompt_version: "v1",
      started_at: "2026-09-12T12:00:00Z",
      finished_at: "2026-09-12T12:01:00Z",
      error: null,
      result: {
        summary: { text: "读其辞。", source_ids: ["s-1"] },
        traditional: [],
        application: { text: "据此行动。", source_ids: [] },
        actions: [],
        citations: [{ source_id: "s-1", quote: "元亨利贞" }],
      },
    },
  ];
  const w = await setup(ReadingView, "/readings/r-1");
  document.body.appendChild(w.element);
  const targets = w.findAll("#source-s-1");
  expect(targets).toHaveLength(1);
  const all = w.get(".all-materials").element as HTMLDetailsElement;
  all.open = false;
  const target = targets[0].element as HTMLElement;
  const scroll = vi.fn();
  target.scrollIntoView = scroll;
  await w.get(".citation").trigger("click");
  await flushPromises();
  expect(all.open).toBe(true);
  expect((target.querySelector("details") as HTMLDetailsElement).open).toBe(
    true,
  );
  expect(document.activeElement).toBe(target);
  expect(scroll).toHaveBeenCalledOnce();
  w.unmount();
});
it("restores a failed pending cast after remount with the same question and request ID", async () => {
  const baseFetch = fetch;
  const casts: any[] = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    if (url === "/api/readings" && init?.method === "POST") {
      casts.push(JSON.parse(String(init.body)));
      throw Error("offline");
    }
    return baseFetch(url, init);
  });
  const first = await setup(CastView);
  await first.get("textarea").setValue("如何安排学习？");
  await first.get('[data-testid="cast"]').trigger("click");
  await flushPromises();
  first.unmount();
  const next = await setup(CastView);
  expect((next.get("textarea").element as HTMLTextAreaElement).value).toBe(
    "如何安排学习？",
  );
  await next.get('[data-testid="cast"]').trigger("click");
  await flushPromises();
  expect(casts[1].request_id).toBe(casts[0].request_id);
  next.unmount();
});
it("uses the same source number across paragraphs and repeated quotes", async () => {
  responseReading.interpretations = [
    {
      id: "a-ok",
      status: "succeeded",
      model: "test",
      prompt_version: "v1",
      started_at: "2026-09-12T12:00:00Z",
      finished_at: "2026-09-12T12:01:00Z",
      error: null,
      result: {
        summary: { text: "先读第二处。", source_ids: ["s-2"] },
        traditional: [],
        application: { text: "再读第一处。", source_ids: ["s-1"] },
        actions: [],
        citations: [
          { source_id: "s-1", quote: "乾。" },
          { source_id: "s-2", quote: "坤。" },
          { source_id: "s-1", quote: "元亨。" },
        ],
      },
    },
  ];
  const w = await setup(ReadingView, "/readings/r-1");
  expect(w.findAll(".citation").map((a) => a.text())).toEqual(["[2]", "[1]"]);
  expect(w.findAll("blockquote a").map((a) => a.text())).toEqual([
    "[1]",
    "[2]",
    "[1]",
  ]);
  w.unmount();
});
it("keeps newly edited reflection text when an earlier save finishes", async () => {
  const baseFetch = fetch;
  let finish!: (response: Response) => void;
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) =>
    url.endsWith("/reflections")
      ? new Promise<Response>((resolve) => {
          finish = resolve;
        })
      : baseFetch(url, init),
  );
  const w = await setup(ReadingView, "/readings/r-1");
  const input = w.get('textarea[aria-label="回看笔记"]');
  await input.setValue("第一段笔记");
  await w.get(".reflection-button").trigger("click");
  await input.setValue("继续写下的新想法");
  finish(
    new Response(
      JSON.stringify({
        id: "note-1",
        text: "第一段笔记",
        created_at: "2026-09-12T12:00:00Z",
      }),
    ),
  );
  await flushPromises();
  expect((input.element as HTMLTextAreaElement).value).toBe("继续写下的新想法");
  expect(w.get(".reflection").text()).toContain("第一段笔记");
  w.unmount();
});
