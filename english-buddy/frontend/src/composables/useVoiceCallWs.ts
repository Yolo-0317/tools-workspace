import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import {
  createLesson,
  DEFAULT_GRADE_ID,
  deleteLesson,
  fetchActiveCalls,
  fetchGrades,
  fetchHealth,
  fetchBuiltinPrewarmStats,
  fetchCustomLessons,
  fetchLessons,
  fetchPrograms,
  type ActiveCallsStats,
  type BuiltinPrewarmStats,
  prewarmLesson,
  type Grade,
  type Lesson,
} from "../api/client";
import { fetchOrtCatalog, type OrtBook } from "../api/ort";
import {
  DEFAULT_PROGRAM_ID,
  getProgramById,
  type Program,
} from "../config/programs";
import {
  AUTO_VOICE_BARGE_IN,
  BARGE_GRACE_MS,
  BARGE_MIN_SPEECH_MS,
  BARGE_SPEECH_THRESHOLD,
  CALL_PREPARE_DELAY_MS,
  loadTtsSpeedPreset,
  MIC_PREPARE_DELAY_MS,
  POST_TTS_LISTEN_GRACE_MS,
  READ_ALONG_MIN_SPEECH_MS,
  READ_ALONG_SILENCE_MS,
  READ_ALONG_UTTERANCE_COOLDOWN_MS,
  saveTtsSpeedPreset,
  ttsSpeedFromPreset,
  TTS_SPEED_PRESETS,
  type TtsSpeedPresetId,
} from "../config/call";
import {
  UTTERANCE_STUCK_TIMEOUT_MS,
  WS_CONNECT_TIMEOUT_MS,
} from "../config/network";
import { wsCallUrl } from "../config/base";
import { useAuth } from "./useAuth";
import { PcmCapture } from "../audio/pcmCapture";
import { unlockAudioOutput, installAudioUnlockListeners } from "../audio/audioUnlock";
import {
  hasPausableTeacherAudio,
  isTeacherAudioPaused,
  pauseTeacherAudio,
  resumeTeacherAudio,
  speakAssistant,
  stopSpeaking,
} from "../audio/speakReply";
import {
  DEFAULT_ORT_LEVEL,
  isOrtGrade,
  ORT_GRADE_IDS,
  ORT_LEVEL_ORDER,
  ortGradeIdForLevel,
  ortLevelFromGradeId,
  type OrtLevelFilter,
} from "../config/ort";
import { ortImageUrl, ortPlaceholderUrl } from "../utils/ortImageUrl";
import {
  findOrtBook,
  ortLinePageIndex,
  ortPageFirstLineIndex,
  ortPageLineOffset as materialLineOffsetForPage,
} from "../utils/ortPage";
import { playChildTurnCue } from "../audio/turnCue";

export type { OrtLevelFilter } from "../config/ort";
export {
  DEFAULT_ORT_LEVEL,
  isOrtGrade,
  ORT_GRADE_IDS,
  ortGradeIdForLevel,
  ortLevelFromGradeId,
} from "../config/ort";

export type CallPhase =
  | "idle"
  | "connecting"
  | "listening"
  | "processing"
  | "speaking"
  | "error";

export type LineVerdict = "pass" | "almost" | "retry";

export type AppScreen =
  | "pick_show"
  | "login"
  | "lesson_manage"
  | "ort_topic"
  | "call";

export type OrtLessonGroup = {
  level: string;
  label: string;
  lessons: Lesson[];
};

type ServerJson =
  | { type: "ready"; model: string; whisper?: { ready: boolean; model: string } }
  | {
      type: "call_started";
      mode: string;
      has_material: boolean;
      stt_enabled?: boolean;
      program?: string;
      program_title?: string;
      program_subtitle?: string;
      program_emoji?: string;
      pronunciation_assess?: boolean;
    }
  | {
      type: "pronunciation_result";
      line_index: number;
      chunk_index: number;
      expected: string;
      spoken: string;
      verdict: LineVerdict;
      score: number;
      advance: boolean;
      message?: string;
    }
  | { type: "status"; phase: string; message?: string }
  | { type: "transcript"; text: string; final: boolean }
  | { type: "assistant_text"; text: string; line_index?: number }
  | { type: "tts_start" }
  | { type: "tts_audio"; audio_base64: string; audio_mime?: string }
  | { type: "tts_failed"; message?: string }
  | { type: "tts_end" }
  | { type: "interrupted" }
  | { type: "lesson_complete" }
  | { type: "reread_line"; line_index: number; text: string }
  | { type: "tts_speed"; tts_speed: number }
  | { type: "set_stt_active"; enabled: boolean }
  | { type: "stt_active"; enabled: boolean }
  | { type: "error"; message: string };

const VERDICT_RANK: Record<LineVerdict, number> = {
  pass: 0,
  almost: 1,
  retry: 2,
};

function mergeLineVerdict(
  current: LineVerdict | undefined,
  next: LineVerdict,
): LineVerdict {
  if (!current) return next;
  return VERDICT_RANK[next] >= VERDICT_RANK[current] ? next : current;
}

function wsUrl(): string {
  return wsCallUrl();
}

export function useVoiceCallWs() {
  const {
    requireAuth,
    sttEnabledForMe,
    sttUsers,
    freeChatEnabledForMe,
    isAuthenticated,
    displayName,
    refreshAuth,
    login: authLogin,
    logout: authLogout,
  } = useAuth();

  const screen = ref<AppScreen>("pick_show");
  const loginReturnTo = ref<"pick_show" | "lesson_manage">("pick_show");
  const postCallScreen = ref<"pick_show" | "ort_topic">("pick_show");
  const ortCatalog = ref<OrtBook[]>([]);
  const ortCatalogLoading = ref(false);
  const ortCatalogError = ref("");
  const ortLevelFilter = ref<OrtLevelFilter>(DEFAULT_ORT_LEVEL);
  const ortSelectedBookId = ref<string | null>(null);
  const ortLessonsCache = ref<Lesson[]>([]);
  const loginUsername = ref("");
  const loginPassword = ref("");
  const loginBusy = ref(false);
  const loginError = ref("");
  const readingMaterial = ref("");
  const typedMessage = ref("");
  const phase = ref<CallPhase>("idle");
  const statusText = ref("选老师、年级和课文即可带读");
  const interimText = ref("");
  const lastAssistant = ref("");
  const errorMessage = ref("");
  const modelName = ref("");
  const whisperModel = ref("");
  const callMode = ref<"read_along" | "free">("read_along");
  const ollamaOk = ref(false);
  const programs = ref<Program[]>([]);
  const grades = ref<Grade[]>([]);
  const gradesLoading = ref(false);
  const lessonsLoading = ref(false);
  const catalogLoadError = ref("");
  const programId = ref(DEFAULT_PROGRAM_ID);
  const activeProgramTitle = ref("");
  const activeProgramEmoji = ref("");
  const lessonDone = ref(false);
  const turnCueKey = ref(0);
  const readAlongLineIndex = ref(0);
  const lineVerdicts = ref<Record<number, LineVerdict>>({});
  const pronunciationAssess = ref(true);
  const micWarning = ref("");
  const lessons = ref<Lesson[]>([]);
  const customLessons = ref<Lesson[]>([]);
  const selectedLessonId = ref<string | null>(null);
  const pickerProgramId = ref(DEFAULT_PROGRAM_ID);
  const pickerGradeId = ref(DEFAULT_GRADE_ID);
  const manageProgramId = ref(DEFAULT_PROGRAM_ID);
  const newLessonTitle = ref("");
  const newLessonText = ref("");
  const lessonManageBusy = ref(false);
  const lessonManageError = ref("");
  const ttsSpeedPreset = ref<TtsSpeedPresetId>(loadTtsSpeedPreset());
  const ttsSpeed = computed(() => ttsSpeedFromPreset(ttsSpeedPreset.value));

  const selectedLesson = computed(() => {
    const id = selectedLessonId.value;
    if (!id) return undefined;
    return (
      lessons.value.find((l) => l.id === id) ??
      ortLessonsCache.value.find((l) => l.id === id)
    );
  });

  function isBuiltinLesson(lesson: Lesson | undefined): boolean {
    return Boolean(lesson?.is_builtin);
  }

  function lessonReadyAtSpeed(lesson: Lesson | undefined, speed: number): boolean {
    if (!lesson) return false;
    if (lesson.prewarm_status !== "ready" || lesson.prewarm_speed == null) {
      return false;
    }
    return Math.abs(lesson.prewarm_speed - speed) < 0.001;
  }

  const builtinPrewarm = ref<BuiltinPrewarmStats | null>(null);
  const activeCalls = ref<ActiveCallsStats>({
    connected: 0,
    calls_started: 0,
    read_along_active: 0,
    read_along_max: 2,
    read_along_full: false,
    free_chat_active: 0,
    free_chat_max: 2,
    free_chat_full: false,
    sessions: [],
  });
  let prewarmPollTimer: ReturnType<typeof setInterval> | null = null;
  let activeCallsPollTimer: ReturnType<typeof setInterval> | null = null;
  let lessonsLoadSeq = 0;

  async function refreshBuiltinPrewarmStats(
    programIdOverride?: string,
  ) {
    const pid = programIdOverride ?? pickerProgramId.value;
    builtinPrewarm.value = await fetchBuiltinPrewarmStats(
      pid,
      ttsSpeed.value,
    );
  }

  function stopPrewarmPoll() {
    if (prewarmPollTimer) {
      clearInterval(prewarmPollTimer);
      prewarmPollTimer = null;
    }
  }

  function applyActiveCalls(next: ActiveCallsStats) {
    const prev = activeCalls.value;
    if (
      prev.connected === next.connected &&
      prev.read_along_active === next.read_along_active &&
      prev.read_along_full === next.read_along_full &&
      prev.free_chat_active === next.free_chat_active &&
      prev.free_chat_full === next.free_chat_full
    ) {
      return;
    }
    activeCalls.value = next;
  }

  async function refreshActiveCalls() {
    applyActiveCalls(await fetchActiveCalls());
  }

  function stopActiveCallsPoll() {
    if (activeCallsPollTimer) {
      clearInterval(activeCallsPollTimer);
      activeCallsPollTimer = null;
    }
  }

  function startActiveCallsPoll() {
    stopActiveCallsPoll();
    void refreshActiveCalls();
    activeCallsPollTimer = setInterval(() => {
      if (screen.value !== "pick_show") return;
      void refreshActiveCalls();
    }, 12000);
  }

  const activeCallsLabel = computed(() => {
    const n = activeCalls.value.connected;
    const r = activeCalls.value.read_along_active;
    const f = activeCalls.value.free_chat_active;
    if (n === 0) return "当前无人在线";
    const parts = [`当前 ${n} 人在线`];
    if (r > 0) parts.push(`${r} 人跟读`);
    if (f > 0) parts.push(`${f} 人聊天`);
    return parts.join(" · ");
  });

  const activeCallsDetail = computed(() => {
    const sessions = activeCalls.value.sessions;
    if (!sessions.length) return "";
    return sessions
      .map((s) => {
        const state = s.call_started
          ? s.call_mode === "read_along"
            ? "跟读中"
            : s.call_mode === "free"
              ? "聊天中"
              : "通话中"
          : "浏览中";
        return `${s.username}（${state}）`;
      })
      .join("、");
  });

  function startPrewarmPoll() {
    stopPrewarmPoll();
    prewarmPollTimer = setInterval(() => {
      if (screen.value !== "pick_show") return;
      void loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value, {
        silent: true,
      });
    }, 30000);
  }

  const isLessonPrewarmReady = computed(() =>
    lessonReadyAtSpeed(selectedLesson.value, ttsSpeed.value),
  );

  const materialLines = computed(() =>
    readingMaterial.value
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean),
  );

  const ortSelectedBook = computed(
    () => ortCatalog.value.find((b) => b.id === ortSelectedBookId.value) ?? null,
  );

  const ortFilteredBooks = computed(() =>
    ortCatalog.value.filter((b) => b.ort_level === ortLevelFilter.value),
  );

  function ortLevelForLessonId(lessonId: string): string {
    const cached =
      ortLessonsCache.value.find((l) => l.id === lessonId) ??
      lessons.value.find((l) => l.id === lessonId);
    if (cached?.grade_id && isOrtGrade(cached.grade_id)) {
      return ortLevelFromGradeId(cached.grade_id);
    }
    const book = ortCatalog.value.find(
      (b) => b.lesson_id === lessonId || b.id === lessonId,
    );
    if (book?.ort_level) return book.ort_level;
    const m = cached?.title.match(/\(L([^)]+)\)/);
    return m?.[1] ?? "";
  }

  function ortBookImagesReady(lessonId: string): boolean {
    const book = ortCatalog.value.find(
      (b) => b.lesson_id === lessonId || b.id === lessonId,
    );
    return Boolean(book?.images_ready);
  }

  const ortIllustratedLessonIds = computed(
    () =>
      new Set(
        ortCatalog.value
          .filter((b) => b.images_ready)
          .map((b) => b.lesson_id || b.id),
      ),
  );

  const ortIllustratedCount = computed(
    () => ortCatalog.value.filter((b) => b.images_ready).length,
  );

  const ortBuiltinLessons = computed(() => {
    if (screen.value === "ort_topic" && ortLessonsCache.value.length) {
      return ortLessonsCache.value;
    }
    if (isOrtGrade(pickerGradeId.value)) {
      return lessons.value.filter((l) => l.is_builtin);
    }
    return ortLessonsCache.value;
  });

  const ortLessonGroups = computed((): OrtLessonGroup[] => {
    const buckets = new Map<string, Lesson[]>();
    for (const lesson of ortBuiltinLessons.value) {
      const level = ortLevelForLessonId(lesson.id) || "?";
      const list = buckets.get(level) ?? [];
      list.push(lesson);
      buckets.set(level, list);
    }
    const order: string[] = [...ORT_LEVEL_ORDER, "?"];
    return order
      .filter((level) => buckets.has(level))
      .map((level) => ({
        level,
        label: level === "?" ? "其他" : `Level ${level}`,
        lessons: buckets.get(level)!,
      }));
  });

  const ortFilteredLessonGroups = computed(() =>
    ortLessonGroups.value.filter((g) => g.level === ortLevelFilter.value),
  );

  const ortActiveBook = computed(() => {
    if (callMode.value !== "read_along") return null;
    const lid = selectedLessonId.value;
    if (!lid?.startsWith("ort_")) return null;
    const book = findOrtBook(ortCatalog.value, lid);
    if (!book?.images_ready) return null;
    return book;
  });

  const readAlongPageIndex = computed(() => {
    const book = ortActiveBook.value;
    if (!book) return 0;
    return ortLinePageIndex(book, readAlongLineIndex.value);
  });

  const ortPageLineOffset = computed(() => {
    const book = ortActiveBook.value;
    if (!book) return 0;
    return materialLineOffsetForPage(book, readAlongPageIndex.value);
  });

  const ortScriptLines = computed(() => {
    const book = ortActiveBook.value;
    if (!book) return null;
    const page = book.pages[readAlongPageIndex.value];
    if (!page) return null;
    const offset = ortPageLineOffset.value;
    return page.lines.map((text, localI) => ({
      text,
      globalIndex: offset + localI,
    }));
  });

  const ortCallPageImage = computed(() => {
    const book = ortActiveBook.value;
    if (!book?.pages.length) return ortPlaceholderUrl();
    const page = book.pages[readAlongPageIndex.value] ?? book.pages[0];
    if (ortFailedImagePaths.value.has(page.image)) {
      return ortPlaceholderUrl();
    }
    return ortImageUrl(page.image);
  });

  const ortCallPageMissing = computed(() => {
    const book = ortActiveBook.value;
    if (!book?.pages.length) return true;
    const page = book.pages[readAlongPageIndex.value] ?? book.pages[0];
    return ortFailedImagePaths.value.has(page.image);
  });

  function onOrtImgError() {
    const book = ortActiveBook.value;
    if (!book?.pages.length) return;
    const page = book.pages[readAlongPageIndex.value] ?? book.pages[0];
    if (!page?.image || ortFailedImagePaths.value.has(page.image)) return;
    const next = new Set(ortFailedImagePaths.value);
    next.add(page.image);
    ortFailedImagePaths.value = next;
  }

  function lineVerdict(index: number): LineVerdict | undefined {
    return lineVerdicts.value[index];
  }

  const selectedProgram = computed(() =>
    getProgramById(programs.value, programId.value),
  );

  async function loadLessonsForGrade(
    gradeId: string,
    programIdOverride?: string,
    opts?: { silent?: boolean },
  ) {
    const pid = programIdOverride ?? pickerProgramId.value;
    const seq = ++lessonsLoadSeq;
    const silent = opts?.silent === true;
    if (!silent) lessonsLoading.value = true;
    try {
      const [list, stats] = await Promise.all([
        fetchLessons(gradeId, pid, ttsSpeed.value),
        fetchBuiltinPrewarmStats(pid, ttsSpeed.value),
      ]);
      if (seq !== lessonsLoadSeq) return list;
      lessons.value = list;
      if (stats) builtinPrewarm.value = stats;
      if (
        !silent &&
        selectedLessonId.value &&
        !list.some((l) => l.id === selectedLessonId.value)
      ) {
        if (list.length) {
          selectLessonOption(list[0].id);
        } else {
          selectedLessonId.value = null;
          readingMaterial.value = "";
        }
      }
      return list;
    } finally {
      if (seq === lessonsLoadSeq && !silent) lessonsLoading.value = false;
    }
  }

  async function loadCustomLessons(programIdOverride?: string) {
    const pid = programIdOverride ?? manageProgramId.value;
    const list = await fetchCustomLessons(pid, ttsSpeed.value);
    customLessons.value = list;
    return list;
  }

  function applyLesson(lesson: Lesson) {
    selectedLessonId.value = lesson.id;
    readingMaterial.value = lesson.text;
  }

  function findLessonById(lessonId: string): Lesson | undefined {
    return (
      lessons.value.find((l) => l.id === lessonId) ??
      ortLessonsCache.value.find((l) => l.id === lessonId)
    );
  }

  function selectLessonOption(value: string) {
    const lesson = findLessonById(value);
    if (lesson) {
      applyLesson(lesson);
      errorMessage.value = "";
    }
  }

  async function loadAllOrtLessons(programIdOverride?: string) {
    const pid = programIdOverride ?? pickerProgramId.value;
    const speed = ttsSpeed.value;
    lessonsLoading.value = true;
    try {
      await loadOrtCatalog();
      const imageReady = ortIllustratedLessonIds.value;
      const [lists, stats] = await Promise.all([
        Promise.all(
          ORT_GRADE_IDS.map((gid) =>
            fetchLessons(gid, pid, speed, { requirePrewarm: false }),
          ),
        ),
        fetchBuiltinPrewarmStats(pid, speed),
      ]);
      ortLessonsCache.value = lists
        .flat()
        .filter((l) => imageReady.has(l.id));
      if (stats) builtinPrewarm.value = stats;
      return ortLessonsCache.value;
    } finally {
      lessonsLoading.value = false;
    }
  }

  function ortLessonReadyForTopic(lesson: Lesson | undefined): boolean {
    if (!lesson) return false;
    if (!ortBookImagesReady(lesson.id)) return false;
    return lessonReadyAtSpeed(lesson, ttsSpeed.value);
  }

  const canStartOrtReadAlong = computed(() => {
    if (readAlongFull.value) return false;
    const lesson = selectedLesson.value;
    if (!lesson?.id.startsWith("ort_")) return false;
    return ortLessonReadyForTopic(lesson);
  });

  async function selectPickerProgram(id: string) {
    pickerProgramId.value = id;
    programId.value = id;
    if (screen.value === "ort_topic") {
      await loadAllOrtLessons(id);
    } else {
      await loadLessonsForGrade(pickerGradeId.value, id);
    }
    if (pickerProgramId.value !== id) return;
  }

  async function selectPickerGrade(id: string) {
    pickerGradeId.value = id;
    if (isOrtGrade(id)) {
      void loadOrtCatalog();
    }
    const keepId = selectedLessonId.value;
    await loadLessonsForGrade(id);
    if (pickerGradeId.value !== id) return;
    if (keepId && lessons.value.some((l) => l.id === keepId)) {
      selectLessonOption(keepId);
    } else if (lessons.value.length) {
      selectLessonOption(lessons.value[0].id);
    } else {
      selectedLessonId.value = null;
      readingMaterial.value = "";
    }
  }

  function openLogin(returnTo: "pick_show" | "lesson_manage" = "pick_show") {
    loginReturnTo.value = returnTo;
    loginError.value = "";
    screen.value = "login";
  }

  async function enterShow(id?: string) {
    const pid = id ?? pickerProgramId.value;
    if (readAlongFull.value) {
      errorMessage.value = readAlongLimitMessage.value;
      return;
    }
    if (!selectedLessonId.value) {
      errorMessage.value = "请先选择课文";
      return;
    }
    if (
      requireAuth.value &&
      !isAuthenticated.value &&
      selectedLesson.value &&
      !selectedLesson.value.is_builtin
    ) {
      errorMessage.value = "自定义课文请先登录";
      openLogin("pick_show");
      return;
    }
    unlockAudioOutput();
    postCallScreen.value = "pick_show";
    programId.value = pid;
    errorMessage.value = "";
    await loadLessonsForGrade(pickerGradeId.value, pid);
    selectLessonOption(selectedLessonId.value);
    await startCall("read_along");
  }

  async function enterFreeChat() {
    if (!freeChatEnabledForMe.value) return;
    if (requireAuth.value && !isAuthenticated.value) {
      errorMessage.value = "自由聊天请先登录";
      openLogin("pick_show");
      return;
    }
    unlockAudioOutput();
    programId.value = pickerProgramId.value;
    errorMessage.value = "";
    await startCall("free");
  }

  async function switchManageProgram(id: string) {
    manageProgramId.value = id;
    await loadCustomLessons(id);
  }

  function openLessonManage(programIdOverride?: string) {
    lessonManageError.value = "";
    manageProgramId.value = programIdOverride ?? pickerProgramId.value;
    screen.value = "lesson_manage";
    void loadCustomLessons(manageProgramId.value);
  }

  async function loadOrtCatalog(force = false) {
    if (ortCatalog.value.length && !force) return;
    ortCatalogLoading.value = true;
    ortCatalogError.value = "";
    try {
      const data = await fetchOrtCatalog();
      ortCatalog.value = data.books ?? [];
    } catch (e) {
      ortCatalogError.value =
        e instanceof Error ? e.message : "牛津阅读树目录加载失败";
    } finally {
      ortCatalogLoading.value = false;
    }
  }

  function goOrtTopic() {
    if (screen.value === "call") return;
    lessonManageError.value = "";
    errorMessage.value = "";
    ortLevelFilter.value = DEFAULT_ORT_LEVEL;
    ortSelectedBookId.value = null;
    screen.value = "ort_topic";
    void loadAllOrtLessons();
  }

  function selectOrtLesson(lessonId: string) {
    ortSelectedBookId.value = lessonId;
    const lesson = findLessonById(lessonId);
    if (lesson) {
      applyLesson(lesson);
      errorMessage.value = "";
    }
  }

  function setOrtLevelFilter(level: OrtLevelFilter) {
    ortLevelFilter.value = level;
    ortSelectedBookId.value = null;
  }

  async function startOrtReadAlong(bookId: string) {
    if (readAlongFull.value) {
      errorMessage.value = readAlongLimitMessage.value;
      return;
    }
    postCallScreen.value = "ort_topic";
    await loadOrtCatalog();
    const book = findOrtBook(ortCatalog.value, bookId);
    if (!book) {
      errorMessage.value = "读本未找到";
      return;
    }
    if (!book.images_ready) {
      errorMessage.value = "该读本暂无页图，请回首页选课文带读";
      return;
    }
    unlockAudioOutput();
    errorMessage.value = "";
    const gradeId = ortGradeIdForLevel(book.ort_level);
    pickerGradeId.value = gradeId;
    programId.value = pickerProgramId.value;
    await loadLessonsForGrade(gradeId, pickerProgramId.value);
    selectLessonOption(book.lesson_id);
    if (!isLessonPrewarmReady.value) {
      errorMessage.value = "课文预热中，请稍后再试";
      return;
    }
    await startCall("read_along");
  }

  function goHome() {
    if (screen.value === "call") {
      endCall();
      return;
    }
    lessonManageError.value = "";
    ortSelectedBookId.value = null;
    screen.value = "pick_show";
    void loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
  }

  function goCustomLessons() {
    if (screen.value === "call") return;
    if (requireAuth.value && !isAuthenticated.value) {
      openLogin("lesson_manage");
      return;
    }
    openLessonManage();
  }

  async function afterAuthLessonsReload() {
    await loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
    if (screen.value === "lesson_manage") {
      await loadCustomLessons(manageProgramId.value);
    }
  }

  async function submitLogin() {
    loginBusy.value = true;
    loginError.value = "";
    try {
      await authLogin(loginUsername.value, loginPassword.value);
      loginPassword.value = "";
      if (loginReturnTo.value === "lesson_manage") {
        openLessonManage();
      } else {
        screen.value = "pick_show";
        errorMessage.value = "";
      }
      await afterAuthLessonsReload();
      await reconnectWs();
    } catch (e) {
      loginError.value = e instanceof Error ? e.message : "登录失败";
    } finally {
      loginBusy.value = false;
    }
  }

  async function handleLogout() {
    await authLogout();
    loginUsername.value = "";
    loginPassword.value = "";
    customLessons.value = [];
    if (
      screen.value === "lesson_manage" ||
      screen.value === "login" ||
      screen.value === "ort_topic"
    ) {
      screen.value = "pick_show";
    }
    await loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
    await reconnectWs();
  }

  async function submitCustomLesson() {
    lessonManageError.value = "";
    lessonManageBusy.value = true;
    try {
      const lesson = await createLesson(
        newLessonTitle.value,
        newLessonText.value,
      );
      newLessonTitle.value = "";
      newLessonText.value = "";
      await loadCustomLessons();
      await loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
      selectLessonOption(lesson.id);
    } catch (e) {
      lessonManageError.value =
        e instanceof Error ? e.message : "保存课文失败";
    } finally {
      lessonManageBusy.value = false;
    }
  }

  async function runLessonPrewarm(lessonId: string) {
    lessonManageError.value = "";
    lessonManageBusy.value = true;
    try {
      await prewarmLesson(lessonId, ttsSpeed.value, manageProgramId.value);
      await loadCustomLessons();
      if (selectedLessonId.value === lessonId) {
        await loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
        selectLessonOption(lessonId);
      }
    } catch (e) {
      lessonManageError.value =
        e instanceof Error ? e.message : "预热失败";
      await loadCustomLessons();
    } finally {
      lessonManageBusy.value = false;
    }
  }

  async function removeCustomLesson(lessonId: string) {
    lessonManageError.value = "";
    lessonManageBusy.value = true;
    try {
      await deleteLesson(lessonId);
      if (selectedLessonId.value === lessonId) {
        selectedLessonId.value = null;
        readingMaterial.value = "";
      }
      await loadCustomLessons();
      await loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
      if (lessons.value.length) {
        selectLessonOption(lessons.value[0].id);
      } else {
        selectedLessonId.value = null;
        readingMaterial.value = "";
      }
    } catch (e) {
      lessonManageError.value =
        e instanceof Error ? e.message : "删除失败";
    } finally {
      lessonManageBusy.value = false;
    }
  }

  function prewarmStatusLabel(lesson: Lesson): string {
    if (lessonReadyAtSpeed(lesson, ttsSpeed.value)) return "已预热";
    if (lesson.prewarm_status === "pending") {
      return `预热中 ${lesson.prewarm_done ?? 0}/${lesson.prewarm_chunks ?? 0}`;
    }
    if (lesson.prewarm_status === "failed") return "预热失败";
    return "未预热";
  }

  function backToPicker() {
    goHome();
  }

  let ws: WebSocket | null = null;
  let presenceReconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let capture: PcmCapture | null = null;
  let callActive = false;
  let callPrepareToken = 0;
  let micPrepareListenOnly = false;
  const callStartedRef = ref(false);
  const rereadFromDone = ref(false);
  let rereadInFlight = false;
  const ttsPlaying = ref(false);
  const teacherPaused = ref(false);
  let processingUtterance = false;
  let utteranceStuckTimer: ReturnType<typeof setTimeout> | null = null;
  let pendingAudioB64: string | undefined;
  let pendingAudioMime = "audio/wav";
  let ttsPlayStartedAt = 0;
  let listenAllowedAfter = 0;
  let utteranceCooldownUntil = 0;
  /**
   * ORT/read-along teacher handoff (client-owned timing):
   * - STT: playAssistantVoice finally → scheduleListenAfterTeacher → child turn
   * - Listen-only: same finally → teacher_playback_done → server auto-advance
   * - Manual nav (下一句/翻页/重读): abortTeacherHandoff() bumps teacherPlaybackEpoch
   *   so the in-flight finally does NOT also hand off (prevents double-advance).
   */
  let listenScheduleToken = 0;
  let listenOnlyAdvancePending = false;
  let teacherPlaybackEpoch = 0;
  const ortFailedImagePaths = ref(new Set<string>());
  const sttEnabled = ref(true);

  const inCall = computed(() => screen.value === "call");

  const listenOnlyHint = computed(() => {
    if (sttEnabledForMe.value) return "";
    const names = sttUsers.value.length
      ? sttUsers.value.join(" / ")
      : "yueyue / dingdang";
    return `当前为只听模式（不识别语音）。请用 ${names} 登录后可跟读、打分。`;
  });

  const ortStartButtonLabel = computed(() =>
    sttEnabledForMe.value ? "开始带读" : "开始听读",
  );

  const readAlongMax = computed(() => activeCalls.value.read_along_max || 2);

  const readAlongFull = computed(
    () =>
      activeCalls.value.read_along_full ||
      activeCalls.value.read_along_active >= readAlongMax.value,
  );

  const readAlongLimitMessage = computed(() =>
    readAlongFull.value
      ? `当前已有 ${readAlongMax.value} 位小朋友在带读，请稍后再试`
      : "",
  );

  const freeChatMax = computed(() => activeCalls.value.free_chat_max || 2);

  const freeChatFull = computed(
    () =>
      activeCalls.value.free_chat_full ||
      activeCalls.value.free_chat_active >= freeChatMax.value,
  );

  const freeChatLimitMessage = computed(() =>
    freeChatFull.value
      ? `当前已有 ${freeChatMax.value} 位小朋友在自由聊天，请稍后再试`
      : "",
  );

  const canStartFreeChat = computed(
    () => freeChatEnabledForMe.value && !freeChatFull.value,
  );

  const canStartReadAlong = computed(
    () =>
      Boolean(selectedLessonId.value) &&
      isLessonPrewarmReady.value &&
      !readAlongFull.value &&
      !lessonsLoading.value &&
      !gradesLoading.value,
  );

  const canInterruptTeacher = computed(
    () =>
      inCall.value &&
      (ttsPlaying.value ||
        phase.value === "speaking" ||
        phase.value === "processing"),
  );

  /** 带读：不识字小朋友靠颜色 + 叮叮声 + 大按钮 */
  const readAlongTurn = computed<
    "teacher" | "child" | "busy" | "done" | null
  >(() => {
    if (callMode.value !== "read_along" || !inCall.value) return null;
    if (teacherPaused.value) return "teacher";
    if (lessonDone.value) return "done";
    if (rereadFromDone.value) {
      if (ttsPlaying.value || phase.value === "speaking") return "teacher";
      if (phase.value === "processing") return "busy";
      if (phase.value === "listening" && sttEnabled.value) return "child";
      return "done";
    }
    // 只听模式：始终显示老师回合，不出现小朋友叮叮/按钮
    if (!sttEnabled.value) {
      if (phase.value === "processing") return "busy";
      return "teacher";
    }
    if (ttsPlaying.value || phase.value === "speaking") return "teacher";
    if (phase.value === "processing") return "busy";
    if (phase.value === "listening") return "child";
    return null;
  });

  const canTapChildDone = computed(
    () =>
      sttEnabled.value &&
      !teacherPaused.value &&
      readAlongTurn.value === "child" &&
      phase.value !== "processing",
  );

  /** 点课文行重读；识别中不可点，老师说话时可点（会打断） */
  const canRereadLine = computed(
    () =>
      callMode.value === "read_along" &&
      inCall.value &&
      callStartedRef.value &&
      (lessonDone.value ||
        (phase.value !== "processing" && phase.value !== "connecting")),
  );

  /** 重读当前句（小朋友回合、读完后；只听模式老师回合也可） */
  const canRepeatCurrentLine = computed(
    () =>
      callStartedRef.value &&
      materialLines.value.length > 0 &&
      (lessonDone.value ||
        readAlongTurn.value === "child" ||
        (!sttEnabled.value && readAlongTurn.value === "teacher")),
  );

  /** 回到上一句（带读中或读完后，第 2 句起） */
  const canBackToPreviousLine = computed(
    () =>
      !rereadFromDone.value &&
      callStartedRef.value &&
      readAlongLineIndex.value > 0 &&
      materialLines.value.length > 0 &&
      (lessonDone.value ||
        readAlongTurn.value === "teacher" ||
        readAlongTurn.value === "child"),
  );

  const canOrtAdvanceLine = computed(
    () =>
      callStartedRef.value &&
      Boolean(ortActiveBook.value) &&
      !lessonDone.value &&
      phase.value !== "connecting" &&
      phase.value !== "processing",
  );

  const canToggleOrtPause = computed(
    () =>
      Boolean(ortActiveBook.value) &&
      callMode.value === "read_along" &&
      inCall.value &&
      callStartedRef.value &&
      !lessonDone.value &&
      (teacherPaused.value ||
        (ttsPlaying.value && hasPausableTeacherAudio())),
  );

  const showReadActionBar = computed(
    () =>
      callMode.value === "read_along" &&
      inCall.value &&
      (canBackToPreviousLine.value ||
        canRepeatCurrentLine.value ||
        (readAlongTurn.value === "child" && sttEnabled.value) ||
        canOrtAdvanceLine.value ||
        canToggleOrtPause.value),
  );

  function invalidateListenSchedule(clearProcessing = false) {
    listenScheduleToken += 1;
    listenOnlyAdvancePending = false;
    if (clearProcessing) clearProcessingUtterance();
  }

  function stopTeacherPlayback() {
    teacherPaused.value = false;
    stopSpeaking();
  }

  /** Stop teacher audio and cancel post-TTS child/listen-only handoff for this playback. */
  function abortTeacherHandoff(clearProcessing = false) {
    teacherPlaybackEpoch += 1;
    invalidateListenSchedule(clearProcessing);
    stopTeacherPlayback();
    ttsPlaying.value = false;
  }

  function toggleOrtTeacherPause() {
    if (!canToggleOrtPause.value) return;
    if (teacherPaused.value || isTeacherAudioPaused()) {
      if (resumeTeacherAudio()) {
        teacherPaused.value = false;
        setPhase(
          "speaking",
          callMode.value === "read_along" && !sttEnabled.value
            ? "老师正在说…"
            : "老师正在说…（说完再跟读；或点「我要说话」）",
        );
      }
      return;
    }
    if (!ttsPlaying.value || !pauseTeacherAudio()) return;
    teacherPaused.value = true;
    invalidateListenSchedule(true);
    setPhase("speaking", "已暂停");
  }

  function ortAdvanceLine() {
    if (!canOrtAdvanceLine.value || !callActive || !callStartedRef.value) return;
    const wasSpeaking = ttsPlaying.value || phase.value === "speaking";
    abortTeacherHandoff(true);
    listenAllowedAfter = 0;
    if (wasSpeaking) {
      sendJson({ type: "interrupt" });
    }
    sendJson({ type: "read_along_advance" });
    setPhase("processing", "下一句…");
  }

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

  function clearUtteranceStuckTimer() {
    if (utteranceStuckTimer) {
      clearTimeout(utteranceStuckTimer);
      utteranceStuckTimer = null;
    }
  }

  function clearProcessingUtterance() {
    processingUtterance = false;
    clearUtteranceStuckTimer();
  }

  function markProcessingUtterance() {
    processingUtterance = true;
    clearUtteranceStuckTimer();
    utteranceStuckTimer = setTimeout(() => {
      utteranceStuckTimer = null;
      if (!processingUtterance || !callActive || !callStartedRef.value) return;
      clearProcessingUtterance();
      if (phase.value === "processing" && !ttsPlaying.value) {
        setPhase("listening", "网络有点慢，请再说一次…");
        if (callMode.value === "read_along") cueChildTurn();
      } else if (phase.value === "listening") {
        statusText.value = "网络有点慢，请再说一次…";
      }
    }, UTTERANCE_STUCK_TIMEOUT_MS);
  }

  function cueChildTurn() {
    if (
      callMode.value !== "read_along" ||
      lessonDone.value ||
      teacherPaused.value
    ) {
      return;
    }
    turnCueKey.value += 1;
    playChildTurnCue();
  }

  function scheduleListenAfterTeacher() {
    if (!callActive || !callStartedRef.value) return;
    const token = ++listenScheduleToken;
    listenAllowedAfter = Date.now() + POST_TTS_LISTEN_GRACE_MS;
    window.setTimeout(() => {
      if (!callActive || !callStartedRef.value || token !== listenScheduleToken) {
        return;
      }
      if (teacherPaused.value || ttsPlaying.value) return;
      clearProcessingUtterance();
      if (callMode.value === "free") {
        setPhase(
          "listening",
          sttEnabled.value ? "轮到你了，请说话…" : "老师说完啦，请打字回复…",
        );
        return;
      }
      if (
        callMode.value === "read_along" &&
        !sttEnabled.value &&
        !lessonDone.value &&
        !rereadInFlight
      ) {
        if (!listenOnlyAdvancePending) {
          listenOnlyAdvancePending = true;
          sendJson({ type: "teacher_playback_done" });
        }
        return;
      }
      if (
        callMode.value === "read_along" &&
        sttEnabled.value &&
        !lessonDone.value
      ) {
        setPhase("listening", "轮到小朋友");
        cueChildTurn();
      }
    }, POST_TTS_LISTEN_GRACE_MS);
  }

  function mapServerPhase(p: string, msg?: string) {
    if (p === "listening" && (ttsPlaying.value || teacherPaused.value)) {
      if (callMode.value === "read_along" && !sttEnabled.value) {
        return;
      }
      if (
        !teacherPaused.value &&
        (callMode.value === "free" || callMode.value === "read_along")
      ) {
        scheduleListenAfterTeacher();
      }
      return;
    }
    if (msg?.includes("课文读完了")) {
      lessonDone.value = true;
      rereadFromDone.value = false;
      clearProcessingUtterance();
    }
    if (msg?.includes("继续跟读")) {
      clearProcessingUtterance();
      utteranceCooldownUntil = 0;
    }
    const labels: Record<string, [CallPhase, string]> = {
      listening: ["listening", msg || "正在听你说…"],
      processing: ["processing", msg || "想一想…"],
      speaking: ["speaking", msg || "老师正在说…"],
      connecting: ["connecting", msg || "接通中…"],
      waiting: ["connecting", msg || "连接成功"],
    };
    const row = labels[p];
    if (row) setPhase(row[0], row[1]);
  }

  function sendJson(payload: object) {
    if (ws?.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify(payload));
    }
  }

  function bargeIn() {
    if (!callActive) return;
    abortTeacherHandoff();
    pendingAudioB64 = undefined;
    sendJson({ type: "interrupt" });
    setPhase("listening", "已打断，请说…");
  }

  function onSpeechStart() {
    if (!AUTO_VOICE_BARGE_IN) return;
    if (!(ttsPlaying.value || phase.value === "speaking")) return;
    if (ttsPlayStartedAt && Date.now() - ttsPlayStartedAt < BARGE_GRACE_MS) {
      return;
    }
    bargeIn();
  }

  function interruptTeacher() {
    bargeIn();
  }

  function submitChildUtterance() {
    if (!callActive || !callStartedRef.value || processingUtterance) return;
    if (callMode.value === "read_along" && lessonDone.value) return;
    if (teacherPaused.value) return;
    if (ttsPlaying.value || phase.value === "speaking") return;
    if (Date.now() < listenAllowedAfter) return;
    if (Date.now() < utteranceCooldownUntil) return;
    if (phase.value !== "listening") return;
    markProcessingUtterance();
    utteranceCooldownUntil =
      Date.now() +
      (callMode.value === "read_along"
        ? READ_ALONG_UTTERANCE_COOLDOWN_MS
        : 2200);
    capture?.resetVad();
    if (ws?.readyState !== WebSocket.OPEN) {
      clearProcessingUtterance();
      setPhase("error", "连接已断开，请返回重试");
      return;
    }
    sendJson({ type: "utterance_end" });
  }

  function onUtteranceEnd() {
    submitChildUtterance();
  }

  function tapChildDone() {
    submitChildUtterance();
  }

  function setTtsSpeedPreset(id: TtsSpeedPresetId) {
    ttsSpeedPreset.value = id;
    saveTtsSpeedPreset(id);
    if (callStartedRef.value && ws?.readyState === WebSocket.OPEN) {
      sendJson({ type: "update_tts_speed", tts_speed: ttsSpeedFromPreset(id) });
    } else if (screen.value === "pick_show") {
      void loadLessonsForGrade(pickerGradeId.value, pickerProgramId.value);
    } else if (screen.value === "lesson_manage") {
      void loadCustomLessons();
    }
  }

  function rereadLine(lineIndex: number) {
    if (!callStartedRef.value || callMode.value !== "read_along") return;
    if (!lessonDone.value && phase.value === "processing") return;
    if (lineIndex < 0 || lineIndex >= materialLines.value.length) return;

    if (lessonDone.value) {
      rereadFromDone.value = true;
    }
    rereadInFlight = true;
    lessonDone.value = false;
    const wasSpeaking = ttsPlaying.value || phase.value === "speaking";
    abortTeacherHandoff(true);
    listenAllowedAfter = 0;
    utteranceCooldownUntil = 0;
    if (wasSpeaking) {
      sendJson({ type: "interrupt" });
    }
    sendJson({ type: "reread_line", line_index: lineIndex });
  }

  function repeatCurrentLine() {
    rereadLine(readAlongLineIndex.value);
  }

  function backToPreviousLine() {
    rereadLine(readAlongLineIndex.value - 1);
  }

  const canOrtPrevPage = computed(
    () =>
      Boolean(ortActiveBook.value) &&
      callStartedRef.value &&
      readAlongPageIndex.value > 0 &&
      canRereadLine.value,
  );

  const canOrtNextPage = computed(() => {
    const book = ortActiveBook.value;
    if (!book || !callStartedRef.value || !canRereadLine.value) return false;
    return readAlongPageIndex.value < book.pages.length - 1;
  });

  function ortGoToPage(pageIndex: number) {
    const book = ortActiveBook.value;
    if (!book || pageIndex < 0 || pageIndex >= book.pages.length) return;
    if (pageIndex === readAlongPageIndex.value) return;
    rereadLine(ortPageFirstLineIndex(book, pageIndex));
  }

  function ortGoToPrevPage() {
    if (!canOrtPrevPage.value) return;
    ortGoToPage(readAlongPageIndex.value - 1);
  }

  function ortGoToNextPage() {
    if (!canOrtNextPage.value) return;
    ortGoToPage(readAlongPageIndex.value + 1);
  }

  async function playAssistantVoice(text: string, audioB64?: string) {
    const playbackEpoch = teacherPlaybackEpoch;
    capture?.resetVad();
    ttsPlaying.value = true;
    ttsPlayStartedAt = Date.now();
    setPhase(
      "speaking",
      callMode.value === "free"
        ? AUTO_VOICE_BARGE_IN
          ? "老师正在说…（大声说话可打断）"
          : "老师正在说…"
        : AUTO_VOICE_BARGE_IN
          ? "老师正在说…（持续大声说话可打断）"
          : "老师正在说…（说完再跟读；或点「我要说话」）",
    );
    try {
      await speakAssistant(text, audioB64, pendingAudioMime);
    } finally {
      teacherPaused.value = false;
      ttsPlaying.value = false;
      pendingAudioB64 = undefined;
      capture?.resetVad();
      if (playbackEpoch === teacherPlaybackEpoch) {
        scheduleListenAfterTeacher();
      }
    }
  }

  function delayMs(ms: number) {
    return new Promise<void>((resolve) => window.setTimeout(resolve, ms));
  }

  /** 通话开始前先走完麦克风授权，再延迟一点发 start_call */
  async function prepareCallEntry(mode: "read_along" | "free"): Promise<void> {
    micPrepareListenOnly = false;
    const prepLabel = mode === "free" ? "准备聊天…" : "准备带读…";
    if (!sttEnabledForMe.value) {
      setPhase("connecting", prepLabel);
      await delayMs(CALL_PREPARE_DELAY_MS);
      return;
    }
    setPhase("connecting", "请允许使用麦克风…");
    micWarning.value = "";
    try {
      await startCapture();
      await delayMs(MIC_PREPARE_DELAY_MS);
    } catch {
      stopCapture();
      micPrepareListenOnly = true;
      micWarning.value =
        "麦克风不可用：请用 HTTPS 打开并允许麦克风。已改为只听模式，可跟老师读。";
      await delayMs(CALL_PREPARE_DELAY_MS);
    }
  }

  async function ensureMicCapture() {
    if (!callActive || !sttEnabled.value) return;
    if (capture) return;
    micWarning.value = "";
    try {
      await startCapture();
    } catch {
      stopCapture();
      micWarning.value =
        "麦克风不可用：手机请用 https://hub.yoloworld.site:8883/english/ 打开，或在浏览器设置里允许麦克风。已改为只听模式，可跟老师读。";
      sttEnabled.value = false;
      sendJson({ type: "set_stt_active", enabled: false });
    }
  }

  async function startCapture() {
    capture?.stop();
    capture = new PcmCapture({
      onPcm: (buf) => {
        if (!ws || ws.readyState !== WebSocket.OPEN || !callActive || !callStartedRef.value) {
          return;
        }
        if (
          ttsPlaying.value ||
          phase.value === "speaking" ||
          phase.value === "processing" ||
          Date.now() < listenAllowedAfter
        ) {
          return;
        }
        ws.send(buf);
      },
      onSpeechStart: AUTO_VOICE_BARGE_IN ? onSpeechStart : undefined,
      onUtteranceEnd,
      speechThreshold: AUTO_VOICE_BARGE_IN
        ? BARGE_SPEECH_THRESHOLD
        : 0.022,
      silenceMs:
        callMode.value === "read_along" ? READ_ALONG_SILENCE_MS : 900,
      minSpeechMs:
        callMode.value === "read_along"
          ? READ_ALONG_MIN_SPEECH_MS
          : AUTO_VOICE_BARGE_IN
            ? BARGE_MIN_SPEECH_MS
            : 360,
    });
    await capture.start();
  }

  function stopCapture() {
    capture?.stop();
    capture = null;
  }

  function handleJson(data: ServerJson) {
    switch (data.type) {
      case "ready":
        modelName.value = data.model;
        whisperModel.value = data.whisper?.model ?? "whisper";
        break;
      case "call_started":
        callStartedRef.value = true;
        callMode.value =
          data.mode === "read_along" ? "read_along" : "free";
        const serverStt = data.stt_enabled ?? sttEnabledForMe.value;
        sttEnabled.value = serverStt && !micPrepareListenOnly;
        pronunciationAssess.value = data.pronunciation_assess ?? true;
        lineVerdicts.value = {};
        activeProgramTitle.value = data.program_title ?? "";
        activeProgramEmoji.value = data.program_emoji ?? "";
        setPhase(
          "speaking",
          callMode.value === "free"
            ? sttEnabled.value
              ? "聊天已开始…"
              : "听老师说…"
            : sttEnabled.value
              ? "带读已开始…"
              : "听老师带读…",
        );
        if (serverStt && micPrepareListenOnly) {
          sendJson({ type: "set_stt_active", enabled: false });
        } else {
          void ensureMicCapture();
        }
        break;
      case "pronunciation_result":
        if (callMode.value === "read_along" && pronunciationAssess.value) {
          lineVerdicts.value = {
            ...lineVerdicts.value,
            [data.line_index]: mergeLineVerdict(
              lineVerdicts.value[data.line_index],
              data.verdict,
            ),
          };
          if (data.advance && rereadFromDone.value) {
            rereadFromDone.value = false;
          }
          if (data.message) {
            statusText.value = data.message;
          }
        }
        break;
      case "status":
        clearProcessingUtterance();
        if (data.phase === "waiting" && callActive) {
          break;
        }
        if (
          callMode.value === "read_along" &&
          data.phase === "processing" &&
          data.message
        ) {
          statusText.value = data.message;
        }
        mapServerPhase(data.phase, data.message);
        break;
      case "transcript":
        interimText.value = data.text;
        break;
      case "assistant_text":
        listenOnlyAdvancePending = false;
        lastAssistant.value = data.text;
        pendingAudioB64 = undefined;
        capture?.resetVad();
        if (
          callMode.value === "read_along" &&
          phase.value === "processing" &&
          !ttsPlaying.value
        ) {
          setPhase("speaking", "听老师念下一句…");
        }
        if (callMode.value === "read_along") {
          if (typeof data.line_index === "number") {
            readAlongLineIndex.value = data.line_index;
          } else {
            const t = data.text.trim();
            const idx = materialLines.value.findIndex(
              (line) =>
                line === t ||
                t.includes(line) ||
                line.includes(t),
            );
            if (idx >= 0) readAlongLineIndex.value = idx;
          }
        }
        break;
      case "tts_start":
        break;
      case "tts_audio":
        pendingAudioB64 = data.audio_base64;
        pendingAudioMime = data.audio_mime || "audio/wav";
        void playAssistantVoice(lastAssistant.value, pendingAudioB64);
        break;
      case "tts_failed":
        rereadInFlight = false;
        void playAssistantVoice(lastAssistant.value);
        break;
      case "tts_end":
        // 带读由 playAssistantVoice.finally → scheduleListenAfterTeacher 统一切回合
        if (
          callMode.value === "free" &&
          callActive &&
          callStartedRef.value
        ) {
          scheduleListenAfterTeacher();
        }
        break;
      case "lesson_complete":
        listenOnlyAdvancePending = false;
        lessonDone.value = true;
        rereadFromDone.value = false;
        rereadInFlight = false;
        clearProcessingUtterance();
        setPhase("listening", "课文读完了，点句子可重读");
        break;
      case "reread_line":
        lessonDone.value = false;
        rereadInFlight = false;
        readAlongLineIndex.value = data.line_index;
        if (pronunciationAssess.value) {
          const next = { ...lineVerdicts.value };
          delete next[data.line_index];
          lineVerdicts.value = next;
        }
        lastAssistant.value = data.text;
        clearProcessingUtterance();
        setPhase("speaking", "老师重读中…");
        break;
      case "tts_speed":
        break;
      case "interrupted":
        abortTeacherHandoff();
        pendingAudioB64 = undefined;
        clearProcessingUtterance();
        if (ortActiveBook.value && phase.value === "processing") {
          setPhase("speaking", "听老师念下一句…");
        }
        break;
      case "stt_active":
        sttEnabled.value = data.enabled;
        break;
      case "error":
        errorMessage.value = data.message;
        if (!callStartedRef.value) {
          callActive = false;
          stopCapture();
          screen.value = "pick_show";
          setPhase("idle", "选老师、年级和课文即可带读");
        } else {
          setPhase("error", data.message);
          callActive = false;
        }
        break;
    }
  }

  function wireWs(socket: WebSocket) {
    socket.onmessage = (ev) => {
      if (typeof ev.data === "string") {
        try {
          handleJson(JSON.parse(ev.data) as ServerJson);
        } catch {
          /* ignore */
        }
      }
    };
    socket.onclose = () => {
      if (ws !== socket) return;
      ws = null;
      if (callActive) {
        callActive = false;
        callStartedRef.value = false;
        rereadInFlight = false;
        rereadFromDone.value = false;
        screen.value = "pick_show";
        setPhase("idle", "连接已断开");
      }
      stopCapture();
      abortTeacherHandoff();
      if (!callActive) {
        schedulePresenceReconnect();
      }
    };
    socket.onerror = () => {
      if (ws !== socket) return;
      if (callActive) {
        setPhase("error", "WebSocket 连接失败");
      }
    };
  }

  function schedulePresenceReconnect() {
    if (presenceReconnectTimer) return;
    presenceReconnectTimer = setTimeout(() => {
      presenceReconnectTimer = null;
      if (!callActive) {
        void ensurePresenceWs();
      }
    }, 3000);
  }

  function waitForWsOpen(timeoutMs: number): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      const socket = ws;
      if (!socket || socket.readyState === WebSocket.CLOSED) {
        resolve(false);
        return;
      }
      if (socket.readyState === WebSocket.OPEN) {
        resolve(true);
        return;
      }
      const timer = setTimeout(() => {
        cleanup();
        resolve(false);
      }, timeoutMs);
      const onOpen = () => {
        cleanup();
        resolve(true);
      };
      const onError = () => {
        cleanup();
        resolve(false);
      };
      const cleanup = () => {
        clearTimeout(timer);
        socket.removeEventListener("open", onOpen);
        socket.removeEventListener("error", onError);
      };
      socket.addEventListener("open", onOpen);
      socket.addEventListener("error", onError);
    });
  }

  async function connectWs(opts?: { silent?: boolean }): Promise<boolean> {
    const state = ws?.readyState;
    if (state === WebSocket.OPEN) return true;
    if (state === WebSocket.CONNECTING) {
      return waitForWsOpen(WS_CONNECT_TIMEOUT_MS);
    }
    const ok = await new Promise<boolean>((resolve) => {
      const socket = new WebSocket(wsUrl());
      ws = socket;
      const timer = setTimeout(() => {
        if (ws === socket && socket.readyState !== WebSocket.OPEN) {
          socket.close();
        }
        cleanup();
        resolve(false);
      }, WS_CONNECT_TIMEOUT_MS);
      const cleanup = () => clearTimeout(timer);
      socket.onopen = () => {
        cleanup();
        resolve(true);
      };
      socket.onerror = () => {
        cleanup();
        resolve(false);
      };
      wireWs(socket);
    });
    if (!ok && !opts?.silent) {
      setPhase("error", "WebSocket 连接超时，请检查网络后重试");
    }
    return ok;
  }

  async function reconnectWs(): Promise<boolean> {
    if (presenceReconnectTimer) {
      clearTimeout(presenceReconnectTimer);
      presenceReconnectTimer = null;
    }
    if (ws) {
      ws.close();
      ws = null;
    }
    await new Promise<void>((resolve) => window.setTimeout(resolve, 80));
    return connectWs({ silent: true });
  }

  async function ensurePresenceWs(): Promise<void> {
    const ok = await connectWs({ silent: true });
    if (ok) void refreshActiveCalls();
  }

  async function startCall(mode: "read_along" | "free" = "read_along") {
    if (mode === "free" && !freeChatEnabledForMe.value) {
      errorMessage.value = "自由聊天仅对指定账号开放";
      return;
    }
    if (mode === "read_along" && readAlongFull.value) {
      errorMessage.value = readAlongLimitMessage.value;
      return;
    }
    if (mode === "free" && freeChatFull.value) {
      errorMessage.value = freeChatLimitMessage.value;
      return;
    }
    unlockAudioOutput();
    errorMessage.value = "";
    if (mode === "read_along" && !selectedLessonId.value) {
      errorMessage.value = "请先选择课文";
      return;
    }
    if (mode === "read_along" && !isLessonPrewarmReady.value) {
      errorMessage.value = "自定义课文请先预热后再带读";
      return;
    }
    if (!ollamaOk.value) {
      const h = await fetchHealth().catch(() => null);
      if (h) {
        modelName.value = h.model;
        ollamaOk.value = h.ollama;
      }
      if (!ollamaOk.value) {
        errorMessage.value = "Ollama 未运行，请先启动并 ollama pull qwen2.5:3b";
        return;
      }
    }

    const ok = await reconnectWs();
    if (!ok) {
      setPhase("error", "无法连接语音服务，请检查网络或稍后重试");
      return;
    }

    if (
      mode === "read_along" &&
      selectedLessonId.value?.startsWith("ort_")
    ) {
      void loadOrtCatalog();
    }

    screen.value = "call";
    callMode.value = mode;
    callActive = true;
    callStartedRef.value = false;
    clearProcessingUtterance();
    lessonDone.value = false;
    turnCueKey.value = 0;
    readAlongLineIndex.value = 0;
    lineVerdicts.value = {};
    ortFailedImagePaths.value = new Set();
    listenOnlyAdvancePending = false;
    micWarning.value = "";
    lastAssistant.value = "";
    interimText.value = "";

    const prepareToken = ++callPrepareToken;
    await prepareCallEntry(mode);
    if (!callActive || prepareToken !== callPrepareToken) {
      return;
    }

    setPhase(
      "connecting",
      mode === "read_along" ? "正在接通带读…" : "正在接通聊天…",
    );
    sendJson({
      type: "start_call",
      lesson_id: mode === "read_along" ? selectedLessonId.value : undefined,
      mode,
      program: programId.value,
      tts_speed: ttsSpeed.value,
    });
  }

  function sendTextMessage() {
    const text = typedMessage.value.trim();
    if (!text || !callStartedRef.value) return;
    if (ttsPlaying.value || phase.value === "speaking") {
      bargeIn();
    }
    typedMessage.value = "";
    markProcessingUtterance();
    interimText.value = text;
    if (ws?.readyState !== WebSocket.OPEN) {
      clearProcessingUtterance();
      setPhase("error", "连接已断开，请返回重试");
      return;
    }
    sendJson({ type: "text_message", text });
  }

  function hangupCallSession(notifyServer = true) {
    const wasLive = callActive || callStartedRef.value;
    callPrepareToken += 1;
    abortTeacherHandoff(true);
    callActive = false;
    callStartedRef.value = false;
    micPrepareListenOnly = false;
    rereadInFlight = false;
    stopCapture();
    if (notifyServer && wasLive && ws?.readyState === WebSocket.OPEN) {
      sendJson({ type: "end_call" });
    }
  }

  function endCall() {
    hangupCallSession(true);
    ortFailedImagePaths.value = new Set();
    interimText.value = "";
    screen.value = postCallScreen.value;
    setPhase(
      "idle",
      postCallScreen.value === "ort_topic"
        ? "选一本牛津阅读树，按页带读"
        : "选老师、年级和课文即可带读",
    );
  }

  function onLeavePage() {
    abortTeacherHandoff();
    if (screen.value === "call" || callActive || callStartedRef.value) {
      endCall();
    }
  }

  function onVisibilityHidden() {
    if (document.visibilityState === "hidden") {
      onLeavePage();
    }
  }

  watch(screen, (next, prev) => {
    if (prev === "call" && next !== "call") {
      abortTeacherHandoff();
      if (callActive || callStartedRef.value) {
        hangupCallSession(true);
      }
    }
  });

  onMounted(() => {
    installAudioUnlockListeners();
    window.addEventListener("pagehide", onLeavePage);
    document.addEventListener("visibilitychange", onVisibilityHidden);
    startPrewarmPoll();
    startActiveCallsPoll();
    void (async () => {
      await refreshAuth();
      gradesLoading.value = true;
      catalogLoadError.value = "";
      try {
        const [plist, glistInitial] = await Promise.all([
          fetchPrograms(),
          fetchGrades(),
        ]);
        programs.value = plist;
        let glist = glistInitial;
        if (!glist.length) {
          await delayMs(800);
          glist = await fetchGrades();
        }
        if (glist.length) {
          grades.value = glist;
        } else {
          grades.value = [
            { id: DEFAULT_GRADE_ID, title: "中班", stage_label: "幼儿园" },
          ];
          catalogLoadError.value = "年级列表加载失败，请点刷新重试";
        }
        if (!grades.value.some((g) => g.id === pickerGradeId.value)) {
          pickerGradeId.value = grades.value[0]?.id ?? DEFAULT_GRADE_ID;
        }
        await selectPickerGrade(pickerGradeId.value);
      } finally {
        gradesLoading.value = false;
      }
    })();
    void fetchHealth()
      .then((h) => {
        modelName.value = h.model;
        ollamaOk.value = h.ollama;
      })
      .catch(() => {});
    void ensurePresenceWs();
    if ("speechSynthesis" in window) {
      window.speechSynthesis.getVoices();
    }
  });

  onUnmounted(() => {
    window.removeEventListener("pagehide", onLeavePage);
    document.removeEventListener("visibilitychange", onVisibilityHidden);
    clearUtteranceStuckTimer();
    stopPrewarmPoll();
    stopActiveCallsPoll();
    if (presenceReconnectTimer) {
      clearTimeout(presenceReconnectTimer);
      presenceReconnectTimer = null;
    }
    hangupCallSession(true);
    ws?.close();
    ws = null;
  });

  return {
    screen,
    readingMaterial,
    typedMessage,
    phase,
    statusText,
    interimText,
    lastAssistant,
    errorMessage,
    modelName,
    whisperModel,
    callMode,
    inCall,
    canStartReadAlong,
    canStartFreeChat,
    freeChatEnabledForMe,
    canInterruptTeacher,
    readAlongTurn,
    turnCueKey,
    materialLines,
    readAlongLineIndex,
    lineVerdict,
    pronunciationAssess,
    micWarning,
    lessons,
    customLessons,
    isBuiltinLesson,
    selectedLessonId,
    selectedLesson,
    isLessonPrewarmReady,
    builtinPrewarm,
    activeCalls,
    activeCallsLabel,
    activeCallsDetail,
    readAlongMax,
    readAlongFull,
    readAlongLimitMessage,
    freeChatMax,
    freeChatFull,
    freeChatLimitMessage,
    rereadFromDone,
    grades,
    gradesLoading,
    lessonsLoading,
    catalogLoadError,
    pickerProgramId,
    pickerGradeId,
    manageProgramId,
    newLessonTitle,
    newLessonText,
    lessonManageBusy,
    lessonManageError,
    selectLessonOption,
    selectPickerProgram,
    selectPickerGrade,
    openLessonManage,
    goHome,
    goCustomLessons,
    openLogin,
    loginReturnTo,
    submitLogin,
    handleLogout,
    loginUsername,
    loginPassword,
    loginBusy,
    loginError,
    requireAuth,
    sttEnabledForMe,
    sttUsers,
    sttEnabled,
    listenOnlyHint,
    ortStartButtonLabel,
    isAuthenticated,
    displayName,
    switchManageProgram,
    submitCustomLesson,
    runLessonPrewarm,
    removeCustomLesson,
    prewarmStatusLabel,
    lessonReadyAtSpeed,
    canTapChildDone,
    canRereadLine,
    canRepeatCurrentLine,
    canBackToPreviousLine,
    showReadActionBar,
    repeatCurrentLine,
    backToPreviousLine,
    tapChildDone,
    canOrtAdvanceLine,
    ortAdvanceLine,
    canToggleOrtPause,
    teacherPaused,
    toggleOrtTeacherPause,
    orbClass,
    startCall,
    endCall,
    sendTextMessage,
    interruptTeacher,
    speechSupported: true,
    ollamaOk,
    programs,
    programId,
    selectedProgram,
    activeProgramTitle,
    activeProgramEmoji,
    enterShow,
    enterFreeChat,
    backToPicker,
    ortCatalog,
    ortCatalogLoading,
    ortCatalogError,
    ortLevelFilter,
    ortSelectedBookId,
    ortSelectedBook,
    ortFilteredBooks,
    ortLessonGroups,
    ortFilteredLessonGroups,
    ortBuiltinLessons,
    ortIllustratedCount,
    ortLessonReadyForTopic,
    canStartOrtReadAlong,
    ortActiveBook,
    readAlongPageIndex,
    ortScriptLines,
    ortCallPageImage,
    ortCallPageMissing,
    onOrtImgError,
    canOrtPrevPage,
    canOrtNextPage,
    ortGoToPrevPage,
    ortGoToNextPage,
    goOrtTopic,
    selectOrtLesson,
    setOrtLevelFilter,
    startOrtReadAlong,
    loadOrtCatalog,
    ttsSpeedPreset,
    ttsSpeed,
    ttsSpeedPresets: TTS_SPEED_PRESETS,
    setTtsSpeedPreset,
    rereadLine,
  };
}
