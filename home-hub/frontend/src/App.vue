<script setup lang="ts">
import { computed, provide, watchEffect } from 'vue'
import { useRoute } from 'vue-router'
import { RouterView } from 'vue-router'
import PwaInstallSheet from './components/PwaInstallSheet.vue'
import { usePwaInstall } from './composables/usePwaInstall'
import { isMobileRoutePath } from './utils/platformRoutes'

const route = useRoute()
const {
  showHint,
  sheetOpen,
  mode,
  hasAndroidPrompt,
  openSheet,
  closeSheet,
  dismissHint,
  installAndroid,
} = usePwaInstall()

const showPwaBanner = computed(
  () => isMobileRoutePath(route.path) && showHint.value,
)

watchEffect(() => {
  document.body.classList.toggle('has-pwa-banner', showPwaBanner.value)
})

provide('openPwaInstall', openSheet)
</script>

<template>
  <div v-if="showPwaBanner" class="pwa-banner">
    <button type="button" class="pwa-banner-main" @click="openSheet">
      添加到主屏幕，像 App 一样打开
    </button>
    <button type="button" class="pwa-banner-close" aria-label="关闭提示" @click="dismissHint">
      ×
    </button>
  </div>

  <RouterView />

  <PwaInstallSheet
    :open="sheetOpen"
    :mode="mode"
    :has-android-prompt="hasAndroidPrompt"
    @close="closeSheet"
    @dismiss="dismissHint"
    @install="installAndroid"
  />
</template>

<style scoped>
.pwa-banner {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 450;
  display: flex;
  align-items: stretch;
  gap: 0;
  padding-top: env(safe-area-inset-top);
  background: #152238;
  border-bottom: 1px solid #2a4060;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
}

.pwa-banner-main {
  flex: 1;
  border: none;
  background: transparent;
  color: #dbe7ff;
  font-size: 13px;
  font-weight: 600;
  text-align: left;
  padding: 10px 12px;
  cursor: pointer;
}

.pwa-banner-close {
  width: 44px;
  border: none;
  background: transparent;
  color: #8b9cb3;
  font-size: 22px;
  line-height: 1;
  cursor: pointer;
}
</style>
