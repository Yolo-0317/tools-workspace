<script setup lang="ts">
import { computed } from "vue";
import type { Material } from "../types";
const props = withDefaults(defineProps<{ material: Material; anchor?: boolean }>(), {
  anchor: true,
});

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

const commentarySections = computed(() =>
  props.material.kind === "commentary"
    ? splitCommentary(props.material.text).map((text) => {
        const noteStart = text.indexOf("〈");
        return noteStart < 0
          ? { lead: text, note: "" }
          : { lead: text.slice(0, noteStart), note: text.slice(noteStart) };
      })
    : [],
);
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
    <div v-if="commentarySections.length" class="classical-sections">
      <p
        v-for="(section, index) in commentarySections"
        :key="index"
        class="classical-text classical-section"
      ><span class="classical-lead">{{ section.lead }}</span><span
          v-if="section.note"
          class="classical-note"
        >{{ section.note }}</span></p>
    </div>
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
