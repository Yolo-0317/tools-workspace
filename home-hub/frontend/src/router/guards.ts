import type { Router } from 'vue-router'
import { getHubAuth, initHubAuth, isAuthenticated } from '../auth/hubAuth'
import { NEWS_ENABLED } from '../config/features'
import {
  defaultHomePath,
  defaultSelectionPath,
  isMobileRoutePath,
  isMobileViewport,
  toDesktopRoute,
  toMobileRoute,
} from '../utils/platformRoutes'

const SHARE_PATHS = new Set(['/selection', '/m/selection'])

/** 未登录可访问（与 backend public_api_prefixes 对应） */
const PUBLIC_PATHS = NEWS_ENABLED ? new Set(['/news', '/m/news']) : new Set<string>()

const CHUNK_RELOAD_KEY = 'hub-chunk-reload-once'

function isStaleChunkError(message: string): boolean {
  return /Failed to fetch dynamically imported module|Importing a module script failed|Loading chunk .* failed/i.test(
    message,
  )
}

export function setupRouterGuards(router: Router) {
  router.onError((error) => {
    const message = error instanceof Error ? error.message : String(error)
    if (!isStaleChunkError(message)) return
    if (sessionStorage.getItem(CHUNK_RELOAD_KEY) === '1') {
      console.error('[router] 资源版本不匹配，已尝试刷新仍失败', error)
      return
    }
    sessionStorage.setItem(CHUNK_RELOAD_KEY, '1')
    console.warn('[router] 检测到过期前端资源，自动刷新', message)
    window.location.reload()
  })

  router.afterEach(() => {
    sessionStorage.removeItem(CHUNK_RELOAD_KEY)
  })

  router.beforeEach(async (to) => {
    const mobileViewport = isMobileViewport()
    const mobileRoute = isMobileRoutePath(to.path)

    if (!NEWS_ENABLED && (to.path === '/news' || to.path === '/m/news')) {
      return { path: defaultHomePath(mobileViewport), replace: true }
    }

    if (to.meta.public) {
      if (to.path === '/login' && isAuthenticated()) {
        return getHubAuth().shareOnly
          ? defaultSelectionPath(mobileViewport)
          : defaultHomePath(mobileViewport)
      }
      return true
    }

    if (!isAuthenticated()) {
      await initHubAuth()
    }
    if (!isAuthenticated()) {
      return { path: '/login', query: { redirect: to.fullPath }, replace: true }
    }

    if (
      getHubAuth().shareOnly &&
      !SHARE_PATHS.has(to.path) &&
      !PUBLIC_PATHS.has(to.path)
    ) {
      return { path: defaultSelectionPath(mobileViewport), replace: true }
    }

    if (mobileViewport && !mobileRoute) {
      const target = toMobileRoute(to.path)
      if (target !== to.path) {
        return { path: target, query: to.query, hash: to.hash, replace: true }
      }
    }

    if (!mobileViewport && mobileRoute) {
      const target = toDesktopRoute(to.path)
      return { path: target, query: to.query, hash: to.hash, replace: true }
    }

    return true
  })
}
