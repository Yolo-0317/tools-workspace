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
  expect(sections[0].get(".classical-note-pronunciation").text()).toBe("音注屯张伦反");
  expect(sections[0].get(".classical-note-block").text()).toBe("卦象震坎皆三画卦");
});

it("把无标点的长篇本义注文拆成音注和有标题的论述段落", () => {
  const note = "〈屯张伦反○震坎皆三画卦之名震一阳动于二隂之下故其德为动其象为雷坎一阳陷于二隂之间故其德为陷为险其象为云为雨为水屯六画卦之名也难也物始生而未通之意故其为字象屮穿地始出而未申也其卦以震遇坎乾坤始交而遇险陷故其名为屯震动在下坎险在上是能动乎险中能动虽可以亨而在险则宜守正而未可遽进故筮得之者其占为大亨而利于正但未可遽有所往耳又初九阳居隂下而为成卦之主是能以贤下人得民而可君之象故筮立君者遇之则吉也〉";
  const wrapper = mount(SourceCard, {
    props: {
      material: {
        id: "zhouyibenyi-3",
        role: "commentary",
        book: "周易本义",
        edition: "四库全书本",
        chapter: "屯·经传注释",
        text: `屯元亨${note}`,
        source_url: "https://example.com",
        checksum: "sha",
        verification: "checked",
        hexagram_id: 3,
        kind: "commentary",
        position: null,
      },
    },
  });

  const annotation = wrapper.get(".classical-note");
  expect(annotation.get(".classical-note-pronunciation").text()).toBe("音注屯张伦反");
  expect(annotation.findAll(".classical-note-block").map((block) => block.get("strong").text())).toEqual([
    "卦象",
    "卦名",
    "卦体",
    "卦势",
    "占断",
    "主爻",
  ]);
  expect(annotation.findAll(".classical-note-block")[1].text()).toContain("屯六画卦之名也");
  expect(annotation.findAll(".classical-note-block")[4].text()).toContain("故筮得之者");
  expect(annotation.text()).not.toContain("〈");
  expect(annotation.text()).not.toContain("〉");
});
