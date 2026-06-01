export const MOBILE_BREAKPOINT_QUERY = '(max-width: 768px)'

export function isMobileViewport(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
}

export function isMobileRoutePath(path: string): boolean {
  return path === '/m' || path.startsWith('/m/')
}

/** 桌面路径 → H5 路径（聊天不进 H5） */
export function toMobileRoute(path: string): string {
  if (path === '/login') return path
  if (isMobileRoutePath(path)) return path
  if (path === '/chat') return '/m'
  if (path === '/') return '/m'
  return `/m${path}`
}

/** H5 路径 → 桌面路径 */
export function toDesktopRoute(path: string): string {
  if (!isMobileRoutePath(path)) return path
  if (path === '/m') return '/'
  return path.slice(2) || '/'
}

export function defaultHomePath(mobile = isMobileViewport()): string {
  return mobile ? '/m' : '/'
}

export function defaultSelectionPath(mobile = isMobileViewport()): string {
  return mobile ? '/m/selection' : '/selection'
}
