import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

/** 仅用于 `npm run build`；日常访问 launchd 单服务 :8780（见 ../README.md） */
export default defineConfig({
  plugins: [vue()],
})
