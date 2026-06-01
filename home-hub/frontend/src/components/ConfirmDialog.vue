<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { usePlatformLayout } from '../composables/usePlatformLayout'

const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message?: string
    confirmLabel?: string
    cancelLabel?: string
    tone?: 'default' | 'warning'
  }>(),
  {
    message: '',
    confirmLabel: '确定',
    cancelLabel: '取消',
    tone: 'default',
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const isMobile = usePlatformLayout()

const panelClass = computed(() => ({
  mobile: isMobile.value,
  warning: props.tone === 'warning',
}))

function onKeydown(event: KeyboardEvent) {
  if (!props.open) return
  if (event.key === 'Escape') {
    event.preventDefault()
    emit('cancel')
  }
}

watch(
  () => props.open,
  (open) => {
    if (open) {
      document.addEventListener('keydown', onKeydown)
      document.body.style.overflow = 'hidden'
    } else {
      document.removeEventListener('keydown', onKeydown)
      document.body.style.overflow = ''
    }
  },
  { immediate: true },
)

onUnmounted(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition name="confirm-fade">
      <div v-if="open" class="confirm-root" :class="{ mobile: isMobile }" role="presentation">
        <button
          type="button"
          class="confirm-backdrop"
          aria-label="关闭"
          @click="emit('cancel')"
        />
        <div
          class="confirm-panel"
          :class="panelClass"
          role="alertdialog"
          aria-modal="true"
          aria-labelledby="confirm-title"
        >
          <div v-if="tone === 'warning'" class="confirm-icon" aria-hidden="true">⚡</div>
          <h2 id="confirm-title" class="confirm-title">{{ title }}</h2>
          <p v-if="message" class="confirm-message">{{ message }}</p>
          <slot />
          <div class="confirm-actions">
            <button type="button" class="confirm-btn cancel" @click="emit('cancel')">
              {{ cancelLabel }}
            </button>
            <button
              type="button"
              class="confirm-btn ok"
              :class="{ warning: tone === 'warning' }"
              @click="emit('confirm')"
            >
              {{ confirmLabel }}
            </button>
          </div>
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.confirm-root {
  position: fixed;
  inset: 0;
  z-index: 400;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  padding-bottom: max(20px, env(safe-area-inset-bottom));
}

.confirm-backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
  cursor: pointer;
}

.confirm-panel {
  position: relative;
  z-index: 1;
  width: min(100%, 360px);
  padding: 22px 20px 18px;
  border-radius: 16px;
  border: 1px solid #243041;
  background: linear-gradient(180deg, #151c26 0%, #121820 100%);
  box-shadow:
    0 24px 48px rgba(0, 0, 0, 0.45),
    inset 0 1px 0 rgba(255, 255, 255, 0.04);
}

.confirm-panel.warning {
  border-color: #4a4020;
  box-shadow:
    0 24px 48px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(252, 211, 77, 0.08);
}

.confirm-panel.mobile {
  width: 100%;
  max-width: none;
  margin-top: auto;
  border-bottom-left-radius: 0;
  border-bottom-right-radius: 0;
  padding-bottom: max(18px, env(safe-area-inset-bottom));
}

.confirm-icon {
  width: 44px;
  height: 44px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  border-radius: 12px;
  font-size: 22px;
  background: rgba(252, 211, 77, 0.12);
  border: 1px solid rgba(252, 211, 77, 0.25);
}

.confirm-title {
  margin: 0 0 10px;
  font-size: 18px;
  font-weight: 600;
  color: #f0f4fa;
  line-height: 1.35;
}

.confirm-message {
  margin: 0 0 20px;
  font-size: 14px;
  line-height: 1.55;
  color: #9aa8bc;
  white-space: pre-line;
}

.confirm-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 10px;
}

.confirm-btn {
  min-height: 44px;
  border-radius: 12px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  -webkit-tap-highlight-color: transparent;
  transition:
    background 0.15s ease,
    border-color 0.15s ease,
    transform 0.1s ease;
}

.confirm-btn:active {
  transform: scale(0.98);
}

.confirm-btn.cancel {
  background: #161e2a;
  border-color: #2a3548;
  color: #b8c5d9;
}

.confirm-btn.cancel:hover {
  background: #1a2432;
  border-color: #3d5270;
}

.confirm-btn.ok {
  background: #2563eb;
  color: #fff;
}

.confirm-btn.ok:hover {
  background: #1d4ed8;
}

.confirm-btn.ok.warning {
  background: linear-gradient(180deg, #fbbf24 0%, #d97706 100%);
  color: #1a1200;
  border-color: #fcd34d;
}

.confirm-btn.ok.warning:hover {
  background: linear-gradient(180deg, #fcd34d 0%, #f59e0b 100%);
}

.confirm-fade-enter-active,
.confirm-fade-leave-active {
  transition: opacity 0.2s ease;
}

.confirm-fade-enter-from,
.confirm-fade-leave-to {
  opacity: 0;
}

.confirm-fade-enter-active .confirm-panel,
.confirm-fade-leave-active .confirm-panel {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}

.confirm-fade-enter-from .confirm-panel,
.confirm-fade-leave-to .confirm-panel {
  transform: scale(0.94) translateY(8px);
}

.confirm-root.mobile.confirm-fade-enter-from .confirm-panel,
.confirm-root.mobile.confirm-fade-leave-to .confirm-panel {
  transform: translateY(100%);
}

@media (max-width: 768px) {
  .confirm-root {
    align-items: flex-end;
    padding: 0;
  }

  .confirm-root.mobile .confirm-panel {
    border-bottom-left-radius: 0;
    border-bottom-right-radius: 0;
  }
}
</style>
