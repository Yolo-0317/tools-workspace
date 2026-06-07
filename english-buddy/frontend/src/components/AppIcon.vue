<script setup lang="ts">
defineProps<{
  name:
    | "hangup"
    | "repeat"
    | "prev"
    | "next"
    | "check"
    | "trash"
    | "pause"
    | "play";
}>();
</script>

<template>
  <svg
    v-if="name === 'hangup'"
    class="app-icon app-icon--hangup"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path
      d="M6.62 10.79c1.44 2.83 3.76 5.14 6.59 6.59l2.2-2.2c.27-.27.67-.36 1.02-.24 1.12.37 2.33.57 3.57.57.55 0 1 .45 1 1V20c0 .55-.45 1-1 1-9.39 0-17-7.61-17-17 0-.55.45-1 1-1h3.5c.55 0 1 .45 1 1 0 1.25.2 2.45.57 3.57.11.35.03.74-.25 1.02l-2.2 2.2z"
    />
  </svg>
  <svg
    v-else-if="name === 'repeat'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M17 2l3 3-3 3"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M20 5H10a5 5 0 0 0-5 5v1"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
    <path
      d="M7 22l-3-3 3-3"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
    <path
      d="M4 19h10a5 5 0 0 0 5-5v-1"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
  </svg>
  <svg
    v-else-if="name === 'prev'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M6 7v10"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
    <path
      d="M10 12H18"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
    <path
      d="M13 9l-3 3 3 3"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'next'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M18 7v10"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
    <path
      d="M14 12H6"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
    />
    <path
      d="M11 9l3 3-3 3"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'check'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="1.75" />
    <path
      d="M8 12.5l2.5 2.5L16 9.5"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
  <svg
    v-else-if="name === 'pause'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <rect x="7" y="6" width="3.5" height="12" rx="0.75" />
    <rect x="13.5" y="6" width="3.5" height="12" rx="0.75" />
  </svg>
  <svg
    v-else-if="name === 'play'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="currentColor"
    aria-hidden="true"
  >
    <path d="M9 7.2v9.6c0 .62.68 1 1.22.68l7.4-4.56a.85.85 0 0 0 0-1.44l-7.4-4.56C9.68 6.2 9 6.58 9 7.2z" />
  </svg>
  <svg
    v-else-if="name === 'trash'"
    class="app-icon"
    viewBox="0 0 24 24"
    fill="none"
    aria-hidden="true"
  >
    <path
      d="M4 7h16M9 7V5a1 1 0 011-1h4a1 1 0 011 1v2M10 11v6M14 11v6M6 7l.8 12.4A1 1 0 007.8 20.5h8.4a1 1 0 001-1.1L18 7"
      stroke="currentColor"
      stroke-width="1.75"
      stroke-linecap="round"
      stroke-linejoin="round"
    />
  </svg>
</template>

<style scoped>
.app-icon {
  display: block;
  width: 1.15em;
  height: 1.15em;
  flex-shrink: 0;
}
</style>
