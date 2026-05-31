import type { Router } from 'vue-router'
import { getHubAuth, initHubAuth, isAuthenticated } from '../auth/hubAuth'

export function setupRouterGuards(router: Router) {
  router.beforeEach(async (to) => {
    if (to.meta.public) {
      if (to.path === '/login' && isAuthenticated()) {
        return getHubAuth().shareOnly ? '/selection' : '/'
      }
      return true
    }

    if (!isAuthenticated()) {
      await initHubAuth()
    }
    if (!isAuthenticated()) {
      return { path: '/login', query: { redirect: to.fullPath }, replace: true }
    }

    if (getHubAuth().shareOnly && to.path !== '/selection') {
      return { path: '/selection', replace: true }
    }
    return true
  })
}
