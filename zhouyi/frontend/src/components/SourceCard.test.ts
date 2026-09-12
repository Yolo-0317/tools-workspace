import { mount } from "@vue/test-utils";
import { expect, it } from "vitest";
import SourceCard from "./SourceCard.vue";

it("把本义合录按经传边界分段且不拆开注文内的圈号", () => {
  const text = "屯元亨〈屯张伦反○震坎皆三画卦〉○彖曰屯刚柔始交〈注〉象曰虽磐桓。○六二屯如邅如乗马班如匪寇婚媾女子贞不字十年乃字〈注〉";
  const wrapper = mount(SourceCard, {
    props: {
      canonicalTexts: ["屯：元亨。", "屯，刚柔始交。", "象曰：虽磐桓。", "六二：屯如邅如，乘马班如，匪寇婚媾，女子贞不字，十年乃字。"],
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
  expect(sections).toHaveLength(4);
  expect(wrapper.get(".commentary-volume").attributes("open")).toBeUndefined();
  expect(wrapper.get(".commentary-volume > summary").text()).toContain("展开本义注疏");
  expect(wrapper.get(".commentary-volume > summary").text()).toContain("4 段");
  expect(sections[0].get(".classical-lead").text()).toBe("元亨。");
  expect(sections[0].get(".classical-section-label").text()).toBe("卦辞");
  expect(sections[1].get(".classical-lead").text()).toBe("屯，刚柔始交。");
  expect(sections[1].get(".classical-section-label").text()).toBe("彖传");
  expect(sections[3].get(".classical-section-label").text()).toBe("六二");
  expect(sections[3].get(".classical-lead").text()).toBe("屯如邅如，乘马班如，匪寇婚媾，女子贞不字，十年乃字。");
  expect(sections[0].get(".classical-note-details").attributes("open")).toBeUndefined();
  expect(sections[0].get(".classical-note-details summary").text()).toBe("查看本义注原文");
  expect(sections[0].get(".classical-note").text()).toBe("〈屯张伦反○震坎皆三画卦〉");
});
