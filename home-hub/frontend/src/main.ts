import { createApp } from 'vue'
import { registerSW } from 'virtual:pwa-register'
import './style.css'
import App from './App.vue'
import router from './router'
import { initHubAuth } from './auth/hubAuth'
import { setupRouterGuards } from './router/guards'

if ('serviceWorker' in navigator) {
  registerSW({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      if (registration) {
        window.setInterval(() => {
          void registration.update()
        }, 60 * 60 * 1000)
      }
    },
    onOfflineReady() {
      console.info('[pwa] 离线壳已就绪')
    },
    onNeedRefresh() {
      console.info('[pwa] 检测到新版本，自动刷新')
      window.location.reload()
    },
  })
}

async function bootstrap() {
  await initHubAuth()
  setupRouterGuards(router)
  createApp(App).use(router).mount('#app')
}

bootstrap()
