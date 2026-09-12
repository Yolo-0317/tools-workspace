import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import SourceCard from "./SourceCard.vue";

it("把本义合录按经传边界分段且不拆开注文内的圈号", () => {
  const text = "屯元亨〈屯张伦反○震坎皆三画卦〉○彖曰屯刚柔始交〈注〉象曰虽磐桓。";
  const wrapper = mount(SourceCard, {
    props: {
      material: {
        id: "zhouyibenyi-3",
        role: "commentary",
        book: "周易本义",
        edition: "四库全书本",
        chapter: "屯·经传注释",
        text,
        source_url: "https://example.com",
        checksum: "sha",
        verification: "checked",
        hexagram_id: 3,
        kind: "commentary",
        position: null,
      },
    },
  });

  const sections = wrapper.findAll(".classical-section");
  expect(sections).toHaveLength(3);
  expect(sections.map((section) => section.text()).join("")).toBe(text);
  expect(sections[0].text()).toContain("反○震坎");
  expect(sections[0].get(".classical-lead").text()).toBe("屯元亨");
  expect(sections[0].get(".classical-note").text()).toBe("〈屯张伦反○震坎皆三画卦〉");
});
