import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { VitePWA } from "vite-plugin-pwa";

const base = process.env.VITE_BASE_PATH || "/english/";

export default defineConfig({
  base,
  plugins: [
    vue(),
    VitePWA({
      registerType: "autoUpdate",
      includeAssets: [
        "favicon.svg",
        "apple-touch-icon.png",
        "pwa-192.png",
        "pwa-512.png",
      ],
      manifest: {
        name: "English Buddy · 英语带读",
        short_name: "English",
        description: "和英语老师语音带读、自由聊天",
        lang: "zh-CN",
        theme_color: "#fff5f8",
        background_color: "#fff5f8",
        display: "standalone",
        orientation: "portrait-primary",
        start_url: base,
        scope: base,
        icons: [
          {
            src: "pwa-192.png",
            sizes: "192x192",
            type: "image/png",
          },
          {
            src: "pwa-512.png",
            sizes: "512x512",
            type: "image/png",
          },
          {
            src: "pwa-512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        skipWaiting: true,
        clientsClaim: true,
        navigateFallback: `${base}index.html`,
        navigateFallbackDenylist: [/^\/api\//, /^\/ws\//],
        // index.html 不预缓存，浏览器/按钮刷新时优先走网络拿最新入口
        globPatterns: ["**/*.{js,css,ico,png,svg,woff2,webmanifest,jpg}"],
        cleanupOutdatedCaches: true,
        runtimeCaching: [
          {
            urlPattern: ({ url }) => url.pathname.includes("/api/"),
            handler: "NetworkOnly",
          },
          {
            urlPattern: ({ url }) => url.pathname.includes("/ws/"),
            handler: "NetworkOnly",
          },
        ],
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  server: {
    host: "127.0.0.1",
    port: 5173,
    proxy: {
      "/api": {
        target: "http://127.0.0.1:18787",
        changeOrigin: true,
      },
      "/ws": {
        target: "ws://127.0.0.1:18787",
        ws: true,
      },
    },
  },
});
