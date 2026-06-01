import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { isMobileRoutePath } from '../utils/platformRoutes'

/** 当前是否为 H5 独立路由（/m/*） */
export function usePlatformLayout() {
  const route = useRoute()
  return computed(
    () => isMobileRoutePath(route.path) || route.meta.mobile === true,
  )
}
