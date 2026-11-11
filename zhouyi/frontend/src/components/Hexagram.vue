<script setup lang="ts">
defineProps<{ bits: string; moving?: number[] }>();
</script>
<template>
  <div
    class="hexagram"
    role="img"
    :aria-label="`卦象，自下而上 ${bits}，变爻 ${moving?.join('、') || '无'}`"
  >
    <div
      v-for="position in [6, 5, 4, 3, 2, 1]"
      :key="position"
      :data-position="position"
      class="hex-line"
      :class="[
        bits[position - 1] === '1' ? 'yang' : 'yin',
        { moving: moving?.includes(position) },
      ]"
    >
      <span /><span /><small v-if="moving?.includes(position)">变</small>
    </div>
  </div>
</template>
