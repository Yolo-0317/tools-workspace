/** 自由聊天入口由服务端 ENGLISH_BUDDY_FREE_CHAT_USERS 控制，前端不再全局开关。 */

/**
 * Voice barge-in while the teacher (TTS) is speaking.
 * Default off: room noise / speaker echo often false-triggers interrupt.
 * Set VITE_AUTO_VOICE_BARGE_IN=true in frontend/.env to re-enable (strict VAD).
 */
export const AUTO_VOICE_BARGE_IN =
  import.meta.env.VITE_AUTO_VOICE_BARGE_IN === "true";

/** After teacher TTS ends, ignore mic briefly (speaker echo / 外放). */
export const POST_TTS_LISTEN_GRACE_MS = 950;

/** 带读：小朋友停顿多久后自动提交识别（VAD） */
export const READ_ALONG_SILENCE_MS = 900;
/** 带读：至少说多久才算有效跟读 */
export const READ_ALONG_MIN_SPEECH_MS = 320;
/** 带读：自动/手动提交后冷却，防 VAD+按钮双发 */
export const READ_ALONG_UTTERANCE_COOLDOWN_MS = 2400;

/** 进入带读页：麦克风授权后再发 start_call，避免弹窗时老师已开读 */
export const MIC_PREPARE_DELAY_MS = 1200;
/** 只听模式（不采麦克风）进入带读前的短暂停顿 */
export const CALL_PREPARE_DELAY_MS = 500;

/** Only used when AUTO_VOICE_BARGE_IN is true. */
export const BARGE_GRACE_MS = 2800;
export const BARGE_SPEECH_THRESHOLD = 0.048;
export const BARGE_MIN_SPEECH_MS = 1100;

export const TTS_SPEED_STORAGE_KEY = "english-buddy-tts-speed";

export const TTS_SPEED_PRESETS = [
  { id: "slow", label: "慢", value: 0.85 },
  { id: "normal", label: "标准", value: 1.0 },
  { id: "fast", label: "快", value: 1.15 },
] as const;

export type TtsSpeedPresetId = (typeof TTS_SPEED_PRESETS)[number]["id"];

export function ttsSpeedFromPreset(id: TtsSpeedPresetId): number {
  return TTS_SPEED_PRESETS.find((p) => p.id === id)?.value ?? 1.0;
}

export function loadTtsSpeedPreset(): TtsSpeedPresetId {
  try {
    const raw = localStorage.getItem(TTS_SPEED_STORAGE_KEY);
    if (raw === "slow" || raw === "normal" || raw === "fast") return raw;
  } catch {
    /* ignore */
  }
  return "normal";
}

export function saveTtsSpeedPreset(id: TtsSpeedPresetId) {
  try {
    localStorage.setItem(TTS_SPEED_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}
