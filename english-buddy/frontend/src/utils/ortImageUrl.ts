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

const preloaded = new Set<string>();

/** Warm browser cache so ORT 页图与 TTS 同步（避免大图解码晚 1～2s） */
export function preloadOrtImageUrls(urls: string[]): void {
  if (typeof Image === "undefined") return;
  for (const url of urls) {
    if (!url || preloaded.has(url)) continue;
    preloaded.add(url);
    const img = new Image();
    img.decoding = "async";
    img.src = url;
  }
}

export function preloadOrtBookPages(
  pages: ReadonlyArray<{ image?: string }>,
  centerPage: number,
  failed?: ReadonlySet<string>,
): void {
  const urls: string[] = [];
  for (const offset of [-1, 0, 1, 2]) {
    const p = pages[centerPage + offset];
    const rel = p?.image?.trim();
    if (!rel || failed?.has(rel)) continue;
    urls.push(ortImageUrl(rel));
  }
  preloadOrtImageUrls(urls);
}
