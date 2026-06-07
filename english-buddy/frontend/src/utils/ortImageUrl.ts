import { APP_BASE } from "../config/base";

export function ortImageUrl(relativePath: string): string {
  const base = APP_BASE.endsWith("/") ? APP_BASE : `${APP_BASE}/`;
  return `${base}ort/${relativePath}`;
}

export function ortPlaceholderUrl(): string {
  const base = APP_BASE.endsWith("/") ? APP_BASE : `${APP_BASE}/`;
  return `${base}ort/placeholder.svg`;
}

export function ortCoverUrl(bookId: string): string {
  return ortImageUrl(`${bookId}/cover.jpg`);
}

export function ortFirstPageUrl(bookId: string): string {
  return ortImageUrl(`${bookId}/p01.jpg`);
}

/** Strip "第N课 · " prefix from lesson picker titles. */
export function ortShortTitle(title: string): string {
  const m = title.match(/^第\s*\d+\s*课\s*·\s*(.+)$/);
  return m ? m[1].trim() : title.trim();
}
