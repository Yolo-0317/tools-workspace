<script setup lang="ts">
import { revealSource } from "../source-navigation";
import type { Paragraph } from "../types";
defineProps<{ paragraph: Paragraph; sourceNumbers: Record<string, number> }>();
</script>
<template>
  <p class="interpretation-text">
    {{ paragraph.text }}
    <a
      v-for="id in paragraph.source_ids"
      :key="id"
      class="citation"
      :href="`#source-${id}`"
      :aria-label="`查看引文 ${sourceNumbers[id]}`"
      @click.prevent="revealSource(id)"
      >[{{ sourceNumbers[id] }}]</a
    >
  </p>
</template>
