/** Play assistant replies as voice (server MP3 preferred, browser TTS fallback). */

import { apiFetch } from "../auth/session";
import { getSharedAudioElement } from "./audioUnlock";

let currentAudio: HTMLAudioElement | null = null;
let speakGen = 0;
let playResolve: (() => void) | null = null;
let pausedByUser = false;

export function hasPausableTeacherAudio(): boolean {
  return currentAudio !== null && !currentAudio.ended;
}

export function isTeacherAudioPaused(): boolean {
  return pausedByUser && hasPausableTeacherAudio();
}

export function pauseTeacherAudio(): boolean {
  if (!hasPausableTeacherAudio() || currentAudio!.paused) return false;
  currentAudio!.pause();
  pausedByUser = true;
  return true;
}

export function resumeTeacherAudio(): boolean {
  if (!pausedByUser || !hasPausableTeacherAudio()) return false;
  pausedByUser = false;
  void currentAudio!.play().catch(() => {
    pausedByUser = true;
  });
  return true;
}

export function stopSpeaking(): void {
  speakGen++;
  pausedByUser = false;
  if (playResolve) {
    const done = playResolve;
    playResolve = null;
    done();
  }
  if (currentAudio) {
    currentAudio.onended = null;
    currentAudio.onerror = null;
    currentAudio.pause();
    currentAudio.removeAttribute("src");
    try {
      currentAudio.load();
    } catch {
      /* */
    }
    currentAudio = null;
  }
  if (typeof window !== "undefined" && "speechSynthesis" in window) {
    window.speechSynthesis.cancel();
  }
}

function playMp3Blob(blob: Blob, onPlaybackStart?: () => void): Promise<void> {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = getSharedAudioElement();
    audio.playbackRate = 1;
    audio.muted = false;
    audio.volume = 1;
    currentAudio = audio;
    let started = false;

    const cleanup = () => {
      if (playResolve === finish) playResolve = null;
      audio.onplaying = null;
      URL.revokeObjectURL(url);
      if (currentAudio === audio) currentAudio = null;
    };

    const finish = () => {
      cleanup();
      resolve();
    };
    playResolve = finish;

    audio.onended = finish;
    audio.onerror = () => {
      cleanup();
      reject(new Error("Audio playback failed"));
    };
    audio.onplaying = () => {
      if (!started) {
        started = true;
        onPlaybackStart?.();
      }
    };

    audio.src = url;
    void audio.play().catch((err) => {
      cleanup();
      reject(err instanceof Error ? err : new Error(String(err)));
    });
  });
}

function playMp3Base64(
  b64: string,
  mime = "audio/mpeg",
  onPlaybackStart?: () => void,
): Promise<void> {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return playMp3Blob(new Blob([bytes], { type: mime }), onPlaybackStart);
}

async function fetchTtsMp3(text: string): Promise<Blob> {
  const res = await apiFetch("api/tts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || res.statusText);
  }
  return res.blob();
}

function speakBrowser(text: string, onPlaybackStart?: () => void): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!("speechSynthesis" in window)) {
      reject(new Error("Browser TTS not supported"));
      return;
    }
    onPlaybackStart?.();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "en-US";
    u.rate = 0.78;
    u.pitch = 1.02;
    const voices = window.speechSynthesis.getVoices();
    const en =
      voices.find((v) => v.name.includes("Samantha")) ||
      voices.find((v) => v.lang.startsWith("en-US")) ||
      voices.find((v) => v.lang.startsWith("en"));
    if (en) u.voice = en;
    u.onend = () => resolve();
    u.onerror = () => reject(new Error("speechSynthesis failed"));
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  });
}

/** Speak assistant text; returns when playback finishes or is interrupted. */
export async function speakAssistant(
  text: string,
  audioBase64?: string,
  audioMime = "audio/wav",
  onPlaybackStart?: () => void,
): Promise<void> {
  const trimmed = text.trim();
  if (!trimmed) return;

  const gen = ++speakGen;
  stopSpeaking();
  speakGen = gen;

  const stillActive = () => gen === speakGen;

  try {
    if (audioBase64) {
      await playMp3Base64(audioBase64, audioMime, onPlaybackStart);
      return;
    }
    const blob = await fetchTtsMp3(trimmed);
    if (!stillActive()) return;
    await playMp3Blob(blob, onPlaybackStart);
  } catch {
    if (!stillActive()) return;
    await speakBrowser(trimmed, onPlaybackStart);
  }
}
