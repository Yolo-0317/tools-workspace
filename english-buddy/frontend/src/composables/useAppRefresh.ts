import { ref } from "vue";

async function clearAllCaches(): Promise<void> {
  if (!("caches" in window)) return;
  const keys = await caches.keys();
  await Promise.all(keys.map((key) => caches.delete(key)));
}

async function unregisterServiceWorkers(): Promise<void> {
  if (!("serviceWorker" in navigator)) return;
  const regs = await navigator.serviceWorker.getRegistrations();
  await Promise.all(regs.map((reg) => reg.unregister()));
}

/** 强制刷新：清 Workbox 缓存、注销 SW，再带 cache-bust 重载（绕过旧 JS bundle） */
export function useAppRefresh() {
  const refreshing = ref(false);

  async function refreshApp() {
    if (refreshing.value) return;
    refreshing.value = true;
    try {
      await clearAllCaches();
      await unregisterServiceWorkers();
    } catch {
      /* ignore */
    }
    const url = new URL(window.location.href);
    url.searchParams.set("_", String(Date.now()));
    window.location.replace(url.toString());
  }

  return { refreshing, refreshApp };
}
