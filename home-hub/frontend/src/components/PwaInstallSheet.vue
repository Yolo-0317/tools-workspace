<script setup lang="ts">
import type { InstallGuideMode } from '../composables/usePwaInstall'

defineProps<{
  open: boolean
  mode: InstallGuideMode
  hasAndroidPrompt?: boolean
}>()

const emit = defineEmits<{
  close: []
  dismiss: []
  install: []
}>()
</script>

<template>
  <Teleport to="body">
    <Transition name="pwa-fade">
      <div v-if="open" class="pwa-root" role="presentation">
        <button type="button" class="pwa-backdrop" aria-label="关闭" @click="emit('close')" />
        <section class="pwa-sheet" role="dialog" aria-modal="true" aria-labelledby="pwa-title">
          <div class="pwa-handle" aria-hidden="true" />
          <h2 id="pwa-title" class="pwa-title">添加到主屏幕</h2>
          <p class="pwa-lead">Safari 没有页面内安装按钮，需要手动添加一次，之后像 App 一样打开。</p>

          <div v-if="mode === 'in-app-browser'" class="pwa-steps warn">
            <p class="step-title">当前在微信等内置浏览器中</p>
            <ol>
              <li>点右上角 <strong>···</strong></li>
              <li>选择 <strong>在 Safari 中打开</strong></li>
              <li>再按下方 Safari 步骤添加到主屏幕</li>
            </ol>
          </div>

          <div v-else-if="mode === 'ios-safari' || mode === 'ios-other'" class="pwa-steps">
            <p class="step-title">iPhone / iPad（Safari）</p>
            <ol>
              <li>
                点底部工具栏中间的
                <span class="share-icon" aria-hidden="true">⎋</span>
                <strong>分享</strong>
                按钮
              </li>
              <li>在弹出面板中<strong>向下滑动</strong></li>
              <li>点 <strong>添加到主屏幕</strong></li>
              <li>右上角点 <strong>添加</strong></li>
            </ol>
            <p v-if="mode === 'ios-other'" class="tip">
              若未看到「添加到主屏幕」，请用系统 Safari 打开（Chrome 等浏览器不支持）。
            </p>
          </div>

          <div v-else-if="mode === 'android'" class="pwa-steps">
            <p class="step-title">Android</p>
            <ol v-if="hasAndroidPrompt">
              <li>点击下方 <strong>立即安装</strong></li>
            </ol>
            <ol v-else>
              <li>点浏览器右上角 <strong>⋮</strong> 菜单</li>
              <li>选择 <strong>添加到主屏幕</strong> 或 <strong>安装应用</strong></li>
            </ol>
          </div>

          <div class="pwa-actions">
            <button
              v-if="mode === 'android' && hasAndroidPrompt"
              type="button"
              class="pwa-btn primary"
              @click="emit('install')"
            >
              立即安装
            </button>
            <button type="button" class="pwa-btn" @click="emit('dismiss')">知道了，不再提示</button>
            <button type="button" class="pwa-btn ghost" @click="emit('close')">关闭</button>
          </div>
        </section>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.pwa-root {
  position: fixed;
  inset: 0;
  z-index: 500;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.pwa-backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(4px);
  -webkit-backdrop-filter: blur(4px);
}

.pwa-sheet {
  position: relative;
  z-index: 1;
  width: min(100%, 420px);
  margin: 0 12px max(12px, env(safe-area-inset-bottom));
  padding: 12px 16px 16px;
  border-radius: 18px;
  border: 1px solid #243041;
  background: linear-gradient(180deg, #151c26 0%, #121820 100%);
  box-shadow: 0 -12px 40px rgba(0, 0, 0, 0.45);
}

.pwa-handle {
  width: 36px;
  height: 4px;
  margin: 0 auto 12px;
  border-radius: 999px;
  background: #314158;
}

.pwa-title {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
  color: #f0f4fa;
}

.pwa-lead {
  margin: 0 0 14px;
  font-size: 13px;
  line-height: 1.55;
  color: #9aa8bc;
}

.pwa-steps {
  margin-bottom: 14px;
  padding: 12px;
  border-radius: 12px;
  background: #0f1419;
  border: 1px solid #243041;
}

.pwa-steps.warn {
  border-color: #6b4f1f;
  background: #1a1408;
}

.step-title {
  margin: 0 0 8px;
  font-size: 13px;
  font-weight: 600;
  color: #dbe7ff;
}

.pwa-steps ol {
  margin: 0;
  padding-left: 18px;
  color: #b8c5d9;
  font-size: 14px;
  line-height: 1.65;
}

.pwa-steps li + li {
  margin-top: 6px;
}

.share-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  margin: 0 2px;
  border-radius: 6px;
  background: #2563eb;
  color: #fff;
  font-size: 14px;
  vertical-align: middle;
}

.tip {
  margin: 10px 0 0;
  font-size: 12px;
  color: #ffd27d;
  line-height: 1.5;
}

.pwa-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.pwa-btn {
  min-height: 44px;
  border-radius: 12px;
  border: 1px solid #2a3548;
  background: #161e2a;
  color: #dbe7ff;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
}

.pwa-btn.primary {
  background: #2563eb;
  border-color: #2563eb;
  color: #fff;
}

.pwa-btn.ghost {
  background: transparent;
  color: #8b9cb3;
  font-weight: 500;
}

.pwa-fade-enter-active,
.pwa-fade-leave-active {
  transition: opacity 0.2s ease;
}

.pwa-fade-enter-active .pwa-sheet,
.pwa-fade-leave-active .pwa-sheet {
  transition: transform 0.22s cubic-bezier(0.32, 0.72, 0, 1);
}

.pwa-fade-enter-from,
.pwa-fade-leave-to {
  opacity: 0;
}

.pwa-fade-enter-from .pwa-sheet,
.pwa-fade-leave-to .pwa-sheet {
  transform: translateY(100%);
}
</style>
