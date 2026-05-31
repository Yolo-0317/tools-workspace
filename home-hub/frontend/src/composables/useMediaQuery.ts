import { onMounted, onUnmounted, ref } from 'vue'

/** 响应式 matchMedia，SSR 安全默认 false */
export function useMediaQuery(query: string) {
  const matches = ref(
    typeof window !== 'undefined' ? window.matchMedia(query).matches : false,
  )
  let mql: MediaQueryList | null = null

  function update() {
    matches.value = mql?.matches ?? false
  }

  onMounted(() => {
    mql = window.matchMedia(query)
    update()
    mql.addEventListener('change', update)
  })

  onUnmounted(() => {
    mql?.removeEventListener('change', update)
  })

  return matches
}

export const MOBILE_QUERY = '(max-width: 768px)'
