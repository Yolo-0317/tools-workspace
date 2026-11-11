import { mount } from "@vue/test-utils";
import { expect, it, vi } from "vitest";
import CyberCast from "./CyberCast.vue";

it("展示六爻进度并允许跳过动画", async () => {
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  const wrapper = mount(CyberCast, {
    props: {
      cast: {
        values: [7, 8, 6, 9, 7, 8],
        moving: [3, 4],
        original_bits: "100110",
        changed_bits: "101010",
        original_id: 1,
        changed_id: 2,
      },
      durationMs: 6000,
    },
  });

  expect(wrapper.findAll("[data-position]")).toHaveLength(6);
  expect(wrapper.text()).toContain("正在生成初爻");
  expect(wrapper.text()).not.toContain("铜钱");
  await wrapper.get('[data-testid="skip-cast-animation"]').trigger("click");
  expect(wrapper.emitted("skip")).toHaveLength(1);
  wrapper.unmount();
});
