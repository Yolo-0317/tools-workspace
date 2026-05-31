import { createApp } from 'vue'
import './style.css'
import App from './App.vue'
import router from './router'
import { initHubAuth } from './auth/hubAuth'
import { setupRouterGuards } from './router/guards'

async function bootstrap() {
  await initHubAuth()
  setupRouterGuards(router)
  createApp(App).use(router).mount('#app')
}

bootstrap()
