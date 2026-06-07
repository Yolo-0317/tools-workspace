<script setup lang="ts">
import { ref, watch } from "vue";
import {
  characterAvatarJpg,
  characterAvatarSvg,
  onAvatarImgError,
} from "../config/characterAvatar";

const props = defineProps<{
  stem: string;
  alt: string;
  size?: "sm" | "md" | "lg" | "xl";
}>();

const src = ref(characterAvatarJpg(props.stem));

watch(
  () => props.stem,
  (stem) => {
    src.value = characterAvatarJpg(stem);
  },
);
</script>

<template>
  <div class="char-avatar-wrap" :class="`char-avatar-wrap--${size ?? 'md'}`">
    <img
      class="char-avatar"
      :src="src"
      :alt="alt"
      loading="lazy"
      decoding="async"
      @error="onAvatarImgError($event, stem)"
    />
  </div>
</template>

<style scoped>
.char-avatar-wrap {
  display: block;
  flex-shrink: 0;
  border-radius: 50%;
  overflow: hidden;
  box-shadow: 0 4px 14px rgba(15, 23, 42, 0.12);
  background: #fff;
}

.char-avatar-wrap--sm {
  width: 2.5rem;
  height: 2.5rem;
}
.char-avatar-wrap--md {
  width: 4.5rem;
  height: 4.5rem;
}
.char-avatar-wrap--lg {
  width: 5.5rem;
  height: 5.5rem;
}
.char-avatar-wrap--xl {
  width: 7.5rem;
  height: 7.5rem;
  box-shadow: 0 8px 24px rgba(15, 23, 42, 0.15);
  border: 3px solid rgba(255, 255, 255, 0.95);
}

.char-avatar {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
  display: block;
}
</style>
