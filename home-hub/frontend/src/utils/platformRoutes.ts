export const MOBILE_BREAKPOINT_QUERY = '(max-width: 768px)'

export function isMobileViewport(): boolean {
  return typeof window !== 'undefined' && window.matchMedia(MOBILE_BREAKPOINT_QUERY).matches
}

export function isMobileRoutePath(path: string): boolean {
  return path === '/m' || path.startsWith('/m/')
}

/** 桌面路径 → H5 路径 */
export function toMobileRoute(path: string): string {
  if (path === '/login') return path
  if (isMobileRoutePath(path)) return path
  if (path === '/' || path === '/advisor') return '/m/advisor'
  return `/m${path}`
}

/** H5 路径 → 桌面路径 */
export function toDesktopRoute(path: string): string {
  if (!isMobileRoutePath(path)) return path
  if (path === '/m' || path === '/m/advisor') return '/advisor'
  return path.slice(2) || '/advisor'
}

export function defaultHomePath(mobile = isMobileViewport()): string {
  return mobile ? '/m/advisor' : '/advisor'
}

/** 投顾总览（与 defaultHomePath 一致，便于链接） */
export function advisorPath(mobile = isMobileViewport()): string {
  return defaultHomePath(mobile)
}

export function defaultSelectionPath(mobile = isMobileViewport()): string {
  return mobile ? '/m/selection' : '/selection'
}
