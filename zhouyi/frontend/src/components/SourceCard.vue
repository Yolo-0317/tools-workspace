<script setup lang="ts">
import type { Material } from "../types";
withDefaults(defineProps<{ material: Material; anchor?: boolean }>(), {
  anchor: true,
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
    <p class="classical-text">{{ material.text }}</p>
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
