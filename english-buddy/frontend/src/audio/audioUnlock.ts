/**
 * Mobile (especially iOS Safari) blocks audio.play() unless unlocked during a user gesture.
 * Call unlockAudioOutput() synchronously from tap/click handlers before any await.
 */

let sharedAudio: HTMLAudioElement | null = null;
let unlocked = false;

/** ~10ms silent WAV */
const SILENT_WAV =
  "data:audio/wav;base64,UklGRigAAABXQVZFZm10IBIAAAABAAEARKwAAIhYAQACABAAAABkYXRhAgAAAAEA";

export function getSharedAudioElement(): HTMLAudioElement {
  if (!sharedAudio) {
    sharedAudio = document.createElement("audio");
    sharedAudio.setAttribute("playsinline", "true");
    sharedAudio.setAttribute("webkit-playsinline", "true");
    sharedAudio.preload = "auto";
    sharedAudio.style.cssText =
      "position:fixed;width:0;height:0;opacity:0;pointer-events:none";
    document.body.appendChild(sharedAudio);
  }
  return sharedAudio;
}

export function isAudioUnlocked(): boolean {
  return unlocked;
}

export function unlockAudioOutput(): void {
  const el = getSharedAudioElement();
  try {
    el.src = SILENT_WAV;
    el.muted = false;
    el.volume = 1;
    const playPromise = el.play();
    if (playPromise) {
      void playPromise
        .then(() => {
          el.pause();
          el.currentTime = 0;
          unlocked = true;
        })
        .catch(() => {
          /* still try real playback later */
        });
    } else {
      unlocked = true;
    }
  } catch {
    /* ignore */
  }
}

/** One-time unlock on first document interaction (backup for mobile). */
export function installAudioUnlockListeners(): void {
  const once = () => unlockAudioOutput();
  document.addEventListener("touchstart", once, { once: true, passive: true });
  document.addEventListener("click", once, { once: true, capture: true });
}
