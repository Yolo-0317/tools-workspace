import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const devApiPort = env.VITE_DEV_API_PORT || env.HUB_DEV_PORT || '8781'

  return {
    plugins: [vue()],
    server: {
      port: 5173,
      proxy: {
        '/api': {
          target: `http://127.0.0.1:${devApiPort}`,
          changeOrigin: true,
        },
      },
    },
  }
})
