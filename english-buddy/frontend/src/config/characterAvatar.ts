import { APP_BASE } from "./base";

/** Character image stem, e.g. `elsa` → /english/characters/elsa.jpg */
export function characterAvatarJpg(stem: string): string {
  return `${APP_BASE}characters/${stem}.jpg`;
}

export function characterAvatarSvg(stem: string): string {
  return `${APP_BASE}characters/${stem}.svg`;
}

export function onAvatarImgError(e: Event, stem: string): void {
  const img = e.target as HTMLImageElement;
  const fallback = characterAvatarSvg(stem);
  if (img.src.endsWith(fallback)) return;
  img.src = fallback;
}
