import { computed, onUnmounted, ref } from "vue";
import {
  fetchHealth,
  fetchReply,
  type HistoryTurn,
} from "../api/client";

export type CallPhase =
  | "idle"
  | "connecting"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

function createRecognition(): SpeechRecognition | null {
  const Ctor = window.webkitSpeechRecognition;
  if (!Ctor) return null;
  const rec = new Ctor();
  rec.lang = "en-US";
  rec.continuous = false;
  rec.interimResults = true;
  return rec;
}

export function useVoiceCall() {
  const phase = ref<CallPhase>("idle");
  const statusText = ref("点击下方开始通话");
  const interimText = ref("");
  const lastAssistant = ref("");
  const errorMessage = ref("");
  const ollamaOk = ref(false);
  const modelName = ref("");

  const history = ref<HistoryTurn[]>([]);
  const recognition = createRecognition();
  let audioEl: HTMLAudioElement | null = null;
  let shouldListenAfterSpeak = false;
  let recognitionActive = false;

  const inCall = computed(
    () =>
      phase.value !== "idle" &&
      phase.value !== "error" &&
      phase.value !== "connecting",
  );

  const orbClass = computed(() => {
    switch (phase.value) {
      case "listening":
        return "orb orb--listen";
      case "processing":
        return "orb orb--think";
      case "speaking":
        return "orb orb--speak";
      case "connecting":
        return "orb orb--connect";
      default:
        return "orb";
    }
  });

  function setPhase(next: CallPhase, text: string) {
    phase.value = next;
    statusText.value = text;
  }

  function stopAudio() {
    if (audioEl) {
      audioEl.pause();
      audioEl.src = "";
      audioEl = null;
    }
  }

  function stopRecognition() {
    if (!recognition || !recognitionActive) return;
    try {
      recognition.abort();
    } catch {
      /* ignore */
    }
    recognitionActive = false;
  }

  function startListening() {
    if (!recognition || phase.value === "idle") return;
    interimText.value = "";
    setPhase("listening", "正在听你说…");
    try {
      recognition.start();
      recognitionActive = true;
    } catch {
      // already started
      recognitionActive = true;
    }
  }

  async function playReplyAudio(b64: string, mime: string) {
    stopAudio();
    const src = `data:${mime};base64,${b64}`;
    audioEl = new Audio(src);
    shouldListenAfterSpeak = true;
    setPhase("speaking", "老师正在说…");
    await new Promise<void>((resolve, reject) => {
      if (!audioEl) return reject(new Error("no audio"));
      audioEl.onended = () => resolve();
      audioEl.onerror = () => reject(new Error("Audio playback failed"));
      audioEl.play().catch(reject);
    });
  }

  async function handleUserUtterance(text: string) {
    const trimmed = text.trim();
    if (!trimmed || phase.value === "idle") return;
    stopRecognition();
    setPhase("processing", "想一想…");
    history.value.push({ role: "user", content: trimmed });
    try {
      const reply = await fetchReply(trimmed, history.value.slice(0, -1));
      lastAssistant.value = reply.text;
      history.value.push({ role: "assistant", content: reply.text });
      await playReplyAudio(reply.audio_base64, reply.audio_mime);
      if (shouldListenAfterSpeak) {
        startListening();
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      errorMessage.value = msg;
      setPhase("error", msg);
      shouldListenAfterSpeak = false;
    }
  }

  function wireRecognition() {
    if (!recognition) return;
    recognition.onstart = () => {
      recognitionActive = true;
    };
    recognition.onresult = (ev: SpeechRecognitionEvent) => {
      let interim = "";
      let final = "";
      for (let i = ev.resultIndex; i < ev.results.length; i++) {
        const t = ev.results[i][0]?.transcript ?? "";
        if (ev.results[i].isFinal) final += t;
        else interim += t;
      }
      interimText.value = interim || final;
      if (final.trim()) {
        void handleUserUtterance(final);
      }
    };
    recognition.onerror = (ev: SpeechRecognitionErrorEvent) => {
      if (ev.error === "aborted" || ev.error === "no-speech") {
        if (phase.value === "listening" && shouldListenAfterSpeak) {
          window.setTimeout(() => startListening(), 400);
        }
        return;
      }
      errorMessage.value = `语音识别: ${ev.error}`;
      setPhase("error", errorMessage.value);
    };
    recognition.onend = () => {
      recognitionActive = false;
      if (phase.value === "listening" && shouldListenAfterSpeak) {
        window.setTimeout(() => startListening(), 300);
      }
    };
  }

  wireRecognition();

  async function startCall() {
    errorMessage.value = "";
    if (!recognition) {
      setPhase(
        "error",
        "当前浏览器不支持语音听写，请用 Chrome 打开本页",
      );
      return;
    }
    setPhase("connecting", "正在连接…");
    try {
      const h = await fetchHealth();
      ollamaOk.value = h.ollama;
      modelName.value = h.model;
      if (!h.ollama) {
        setPhase(
          "error",
          "Ollama 未运行或不可用，请先启动 Ollama 并拉取模型",
        );
        return;
      }
    } catch {
      setPhase("error", "无法连接后端，请先运行 scripts/dev-backend.sh");
      return;
    }
    history.value = [];
    lastAssistant.value = "";
    shouldListenAfterSpeak = true;
    try {
      setPhase("processing", "老师正在接入…");
      const greeting = await fetchReply(
        "(Voice call just connected.) Give a warm 2-sentence English greeting and one very easy question for a child.",
        [],
      );
      lastAssistant.value = greeting.text;
      history.value.push({
        role: "user",
        content: "[Call connected]",
      });
      history.value.push({ role: "assistant", content: greeting.text });
      await playReplyAudio(greeting.audio_base64, greeting.audio_mime);
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      errorMessage.value = msg;
      setPhase("error", msg);
      return;
    }
    if (shouldListenAfterSpeak) startListening();
  }

  function endCall() {
    shouldListenAfterSpeak = false;
    stopRecognition();
    stopAudio();
    interimText.value = "";
    setPhase("idle", "通话已结束");
  }

  onUnmounted(() => {
    endCall();
  });

  return {
    phase,
    statusText,
    interimText,
    lastAssistant,
    errorMessage,
    ollamaOk,
    modelName,
    inCall,
    orbClass,
    startCall,
    endCall,
    speechSupported: !!recognition,
  };
}
