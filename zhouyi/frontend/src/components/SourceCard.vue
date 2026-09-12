<script setup lang="ts">
import { computed } from "vue";
import type { Material } from "../types";
const props = withDefaults(
  defineProps<{
    material: Material;
    anchor?: boolean;
    canonicalTexts?: string[];
  }>(),
  { anchor: true, canonicalTexts: () => [] },
);

const punctuation = /[\s，。；：、！？“”‘’（）〈〉《》·—…,.!?;:'"()\-]/u;
const displayVariants: Record<string, string> = {
  "乗": "乘",
  "囘": "回",
};
function comparisonCharacter(character: string) {
  return displayVariants[character] || character;
}
function restorePunctuation(text: string, sources: string[]) {
  const target = Array.from(text)
    .filter((character) => !punctuation.test(character))
    .map(comparisonCharacter)
    .join("");
  if (!target) return text;
  for (const source of sources) {
    let normalized = "";
    const positions: number[] = [];
    for (let index = 0; index < source.length; index += 1) {
      const character = source[index];
      if (!punctuation.test(character)) {
        normalized += comparisonCharacter(character);
        positions.push(index);
      }
    }
    const startIndex = normalized.indexOf(target);
    if (startIndex < 0) continue;
    const start = positions[startIndex];
    let end = positions[startIndex + target.length - 1] + 1;
    while (end < source.length && punctuation.test(source[end])) end += 1;
    return source.slice(start, end).trim();
  }
  return text;
}

function splitCommentary(text: string) {
  const sections: string[] = [];
  let current = "";
  let noteDepth = 0;
  const finish = () => {
    const value = current.trim();
    if (value) sections.push(value);
    current = "";
  };

  for (const character of text.replaceAll("\r", "")) {
    if (character === "\n" && noteDepth === 0) {
      finish();
      continue;
    }
    if (character === "○" && noteDepth === 0 && current.trim()) finish();
    current += character;
    if (character === "〈") noteDepth += 1;
    if (character === "〉" && noteDepth > 0) {
      noteDepth -= 1;
      if (noteDepth === 0) finish();
    }
  }
  finish();
  return sections;
}

const commentarySections = computed(() => {
  if (props.material.kind !== "commentary") return [];
  const hexagramName = props.material.chapter.split("·")[0];
  let context = "卦辞";
  let currentLine = "";
  return splitCommentary(props.material.text).map((text) => {
    const marked = text.startsWith("○");
    const cleanText = marked ? text.slice(1) : text;
    const noteStart = cleanText.indexOf("〈");
    let lead = noteStart < 0 ? cleanText : cleanText.slice(0, noteStart);
    const note = noteStart < 0 ? "" : cleanText.slice(noteStart);
    let label = context;
    if (marked && lead.startsWith("彖曰")) {
      context = label = "彖传";
      lead = lead.slice(2);
    } else if (marked && lead.startsWith("象曰")) {
      context = label = "大象";
      lead = lead.slice(2);
    } else {
      const line = lead.match(/^(初[六九]|[六九][二三四五]|上[六九])/);
      if (line) {
        currentLine = line[0];
        context = label = currentLine;
        lead = lead.slice(currentLine.length);
      } else if (!marked && lead.startsWith("象曰")) {
        label = currentLine ? `${currentLine}小象` : "小象";
        lead = lead.slice(2);
      } else if (label === "卦辞" && lead.startsWith(hexagramName)) {
        lead = lead.slice(hexagramName.length);
      }
    }
    return { label, lead: restorePunctuation(lead, props.canonicalTexts), note };
  });
});
function safeUrl(url: string) {
  try {
    const u = new URL(url);
    return ["https:", "http:"].includes(u.protocol) ? u.href : undefined;
  } catch {
    return undefined;
  }
}
</script>
<template>
  <article
    :id="anchor ? `source-${material.id}` : undefined"
    tabindex="-1"
    class="source-card"
    :class="{ primary: material.role === 'primary' }"
  >
    <div class="source-meta">
      <span>{{ material.book }} · {{ material.chapter }}</span
      ><span v-if="material.role === 'primary'">主读</span>
    </div>
    <details v-if="commentarySections.length" class="commentary-volume">
      <summary><span>展开本义注疏</span><small>{{ commentarySections.length }} 段 · 按需阅读</small></summary>
      <div class="classical-sections">
        <section
          v-for="(section, index) in commentarySections"
          :key="index"
          class="classical-text classical-section"
        ><span class="classical-section-label">{{ section.label }}</span
          ><p class="classical-lead">{{ section.lead }}</p
          ><details v-if="section.note" class="classical-note-details"
            ><summary>查看本义注原文</summary
            ><p class="classical-note">{{ section.note }}</p></details
          ></section>
      </div>
    </details>
    <p v-else class="classical-text">{{ material.text }}</p>
    <details>
      <summary>版本与出处</summary>
      <p>{{ material.edition }} · 已检查来源与文本结构，尚未逐字校勘</p>
      <a
        v-if="safeUrl(material.source_url)"
        :href="safeUrl(material.source_url)"
        target="_blank"
        rel="noopener noreferrer"
        >核对原文</a
      >
      <p v-if="material.display_note">{{ material.display_note }}</p>
    </details>
  </article>
</template>
