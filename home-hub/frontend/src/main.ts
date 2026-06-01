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
    onOfflineReady() {
      console.info('[pwa] 离线壳已就绪')
    },
    onNeedRefresh() {
      console.info('[pwa] 有新版本，刷新页面即可更新')
    },
  })
}

async function bootstrap() {
  await initHubAuth()
  setupRouterGuards(router)
  createApp(App).use(router).mount('#app')
}

bootstrap()
