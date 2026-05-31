<script setup lang="ts">
defineProps<{
  role: 'user' | 'assistant' | 'system'
  content: string
  streaming?: boolean
}>()
</script>

<template>
  <article class="bubble" :class="role">
    <header>{{ role === 'user' ? '你' : role === 'system' ? '系统' : '助手' }}</header>
    <p class="content">{{ content }}<span v-if="streaming" class="cursor">▍</span></p>
  </article>
</template>

<style scoped>
.bubble {
  max-width: min(720px, 92%);
  padding: 12px 14px;
  border-radius: 14px;
  border: 1px solid #243041;
  background: #121820;
}

@media (max-width: 768px) {
  .bubble {
    max-width: 88%;
    padding: 10px 12px;
    border-radius: 16px;
  }

  .bubble.user header,
  .bubble.assistant header {
    display: none;
  }

  .bubble.user {
    max-width: 84%;
    border-bottom-right-radius: 6px;
  }

  .bubble.assistant {
    max-width: 92%;
    border-bottom-left-radius: 6px;
  }

  .bubble.system header {
    display: block;
    margin-bottom: 4px;
  }

  .content {
    font-size: 15px;
    line-height: 1.6;
  }
}

.bubble.user {
  align-self: flex-end;
  background: #1a2740;
  border-color: #2f4570;
}

.bubble.system {
  align-self: stretch;
  max-width: 100%;
  background: #261010;
  border-color: #6b2a2a;
  color: #ffb4b4;
}

.bubble.system header {
  color: #ff8f8f;
}

.bubble.assistant {
  align-self: flex-start;
}

header {
  font-size: 11px;
  color: #8b9cb3;
  margin-bottom: 6px;
}

.content {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.55;
}

.cursor {
  animation: blink 1s step-end infinite;
}

@keyframes blink {
  50% {
    opacity: 0;
  }
}
</style>
