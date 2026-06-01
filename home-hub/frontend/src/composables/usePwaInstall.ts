import { computed, onMounted, onUnmounted, ref } from 'vue'

const DISMISS_KEY = 'hub-pwa-install-dismissed'

export type InstallGuideMode = 'ios-safari' | 'ios-other' | 'in-app-browser' | 'android' | 'desktop' | 'none'

function detectMode(): InstallGuideMode {
  if (typeof window === 'undefined') return 'none'

  const ua = navigator.userAgent
  const isIOS =
    /iPad|iPhone|iPod/.test(ua) ||
    (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1)

  if (/MicroMessenger|wxwork|QQ\//i.test(ua)) {
    return 'in-app-browser'
  }

  if (/android/i.test(ua)) {
    return 'android'
  }

  if (isIOS) {
    const isSafari =
      /Safari/i.test(ua) &&
      !/CriOS|FxiOS|EdgiOS|OPiOS|DuckDuckGo/i.test(ua)
    return isSafari ? 'ios-safari' : 'ios-other'
  }

  if (/Macintosh|Windows|Linux/i.test(ua) && !/Mobile/i.test(ua)) {
    return 'desktop'
  }

  return 'none'
}

function isStandaloneMode(): boolean {
  if (typeof window === 'undefined') return false
  return (
    window.matchMedia('(display-mode: standalone)').matches ||
    (navigator as Navigator & { standalone?: boolean }).standalone === true
  )
}

export function usePwaInstall() {
  const mode = ref<InstallGuideMode>('none')
  const sheetOpen = ref(false)
  const deferredPrompt = ref<BeforeInstallPromptEvent | null>(null)
  const dismissed = ref(false)

  const canInstall = computed(
    () => !isStandaloneMode() && mode.value !== 'none' && mode.value !== 'desktop',
  )

  const showHint = computed(() => canInstall.value && !dismissed.value)

  function refreshMode() {
    mode.value = detectMode()
  }

  function openSheet() {
    if (!canInstall.value) return
    sheetOpen.value = true
  }

  function closeSheet() {
    sheetOpen.value = false
  }

  function dismissHint() {
    dismissed.value = true
    sheetOpen.value = false
    try {
      localStorage.setItem(DISMISS_KEY, String(Date.now()))
    } catch {
      /* ignore */
    }
  }

  async function installAndroid() {
    const prompt = deferredPrompt.value
    if (!prompt) {
      openSheet()
      return
    }
    prompt.prompt()
    await prompt.userChoice
    deferredPrompt.value = null
    sheetOpen.value = false
  }

  function onBeforeInstallPrompt(event: Event) {
    event.preventDefault()
    deferredPrompt.value = event as BeforeInstallPromptEvent
  }

  onMounted(() => {
    refreshMode()
    try {
      const raw = localStorage.getItem(DISMISS_KEY)
      if (raw) {
        const ts = Number(raw)
        // 7 天后可再次提示
        dismissed.value = Number.isFinite(ts) && Date.now() - ts < 7 * 86400000
      }
    } catch {
      dismissed.value = false
    }
    window.addEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  })

  onUnmounted(() => {
    window.removeEventListener('beforeinstallprompt', onBeforeInstallPrompt)
  })

  return {
    mode,
    sheetOpen,
    canInstall,
    showHint,
    hasAndroidPrompt: computed(() => deferredPrompt.value !== null),
    openSheet,
    closeSheet,
    dismissHint,
    installAndroid,
  }
}
