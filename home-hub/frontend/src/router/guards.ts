import type { Router } from 'vue-router'
import { getHubAuth, initHubAuth, isAuthenticated } from '../auth/hubAuth'
import {
  defaultHomePath,
  defaultSelectionPath,
  isMobileRoutePath,
  isMobileViewport,
  toDesktopRoute,
  toMobileRoute,
} from '../utils/platformRoutes'

const SHARE_PATHS = new Set(['/selection', '/m/selection'])

export function setupRouterGuards(router: Router) {
  router.beforeEach(async (to) => {
    const mobileViewport = isMobileViewport()
    const mobileRoute = isMobileRoutePath(to.path)

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

    if (getHubAuth().shareOnly && !SHARE_PATHS.has(to.path)) {
      return { path: defaultSelectionPath(mobileViewport), replace: true }
    }

    if (mobileViewport && !mobileRoute && to.path !== '/chat') {
      const target = toMobileRoute(to.path)
      if (target !== to.path) {
        return { path: target, query: to.query, hash: to.hash, replace: true }
      }
    }

    if (mobileViewport && to.path === '/chat') {
      return { path: '/m', replace: true }
    }

    if (!mobileViewport && mobileRoute) {
      const target = toDesktopRoute(to.path)
      return { path: target, query: to.query, hash: to.hash, replace: true }
    }

    return true
  })
}
