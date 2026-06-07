import { createApp } from "vue";
import { registerSW } from "virtual:pwa-register";
import App from "./App.vue";
import "./styles/global.css";

if ("serviceWorker" in navigator) {
  registerSW({
    immediate: true,
    onRegisteredSW(_swUrl, registration) {
      if (registration) {
        window.setInterval(() => {
          void registration.update();
        }, 60 * 60 * 1000);
        document.addEventListener("visibilitychange", () => {
          if (document.visibilityState === "visible") {
            void registration.update();
          }
        });
      }
    },
    onNeedRefresh() {
      window.location.reload();
    },
  });
}

// 强制刷新留下的 ?_= 时间戳，恢复干净 URL
{
  const url = new URL(window.location.href);
  if (url.searchParams.has("_")) {
    url.searchParams.delete("_");
    const next = `${url.pathname}${url.search}${url.hash}`;
    window.history.replaceState(null, "", next || url.pathname);
  }
}

createApp(App).mount("#app");
