<script setup lang="ts">
import { computed, ref } from "vue";
import AppIcon from "../components/AppIcon.vue";
import CharacterAvatar from "../components/CharacterAvatar.vue";
import { useAppRefresh } from "../composables/useAppRefresh";
import { useVoiceCallWs } from "../composables/useVoiceCallWs";
import type { Program } from "../config/programs";
import OrtTopicView from "./OrtTopicView.vue";

const {
  screen,
  readingMaterial,
  typedMessage,
  phase,
  statusText,
  interimText,
  lastAssistant,
  errorMessage,
  modelName,
  callMode,
  inCall,
  canStartReadAlong,
  canStartFreeChat,
  enterFreeChat,
  freeChatEnabledForMe,
  orbClass,
  endCall,
  sendTextMessage,
  interruptTeacher,
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
  goHome,
  goCustomLessons,
  openLogin,
  loginReturnTo,
  switchManageProgram,
  submitCustomLesson,
  runLessonPrewarm,
  removeCustomLesson,
  prewarmStatusLabel,
  lessonReadyAtSpeed,
  ttsSpeed,
  canTapChildDone,
  tapChildDone,
  canOrtAdvanceLine,
  ortAdvanceLine,
  canToggleOrtPause,
  teacherPaused,
  toggleOrtTeacherPause,
  canRereadLine,
  showReadActionBar,
  rereadLine,
  canRepeatCurrentLine,
  canBackToPreviousLine,
  repeatCurrentLine,
  backToPreviousLine,
  ttsSpeedPreset,
  ttsSpeedPresets,
  setTtsSpeedPreset,
  ollamaOk,
  programs,
  selectedProgram,
  activeProgramTitle,
  activeProgramEmoji,
  enterShow,
  submitLogin,
  handleLogout,
  loginUsername,
  loginPassword,
  loginBusy,
  loginError,
  requireAuth,
  sttEnabledForMe,
  sttEnabled,
  listenOnlyHint,
  ortStartButtonLabel,
  isAuthenticated,
  displayName,
  activeCallsLabel,
  activeCallsDetail,
  activeCalls,
  readAlongFull,
  readAlongLimitMessage,
  freeChatFull,
  freeChatLimitMessage,
  rereadFromDone,
  ortCatalogLoading,
  ortCatalogError,
  ortLevelFilter,
  ortSelectedBookId,
  ortFilteredLessonGroups,
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
  ortIllustratedCount,
  ortLessonReadyForTopic,
  canStartOrtReadAlong,
} = useVoiceCallWs();

const ortSwipeStartX = ref(0);
const ortSwipeStartY = ref(0);

function onOrtPageTouchStart(e: TouchEvent) {
  if (e.touches.length !== 1) return;
  ortSwipeStartX.value = e.touches[0].clientX;
  ortSwipeStartY.value = e.touches[0].clientY;
}

function onOrtPageTouchEnd(e: TouchEvent) {
  if (e.changedTouches.length !== 1) return;
  const dx = e.changedTouches[0].clientX - ortSwipeStartX.value;
  const dy = e.changedTouches[0].clientY - ortSwipeStartY.value;
  if (Math.abs(dx) < 48 || Math.abs(dx) < Math.abs(dy) * 1.25) return;
  if (dx < 0) ortGoToNextPage();
  else ortGoToPrevPage();
}

const { refreshing, refreshApp } = useAppRefresh();

async function refreshFromCall() {
  if (inCall.value) {
    endCall();
  }
  await refreshApp();
}

const skin = computed(() => selectedProgram.value?.page.skin ?? "");

const usesThemedShell = computed(
  () => screen.value === "call",
);

const appStyle = computed(() => {
  const p = selectedProgram.value;
  if (!p || !usesThemedShell.value) return {};
  return {
    "--accent": p.theme.accent,
    "--accent2": p.theme.accent2 ?? p.theme.accent,
    "--btn-primary": p.page.btn_primary,
    "--btn-shadow": p.page.btn_shadow,
    "--hero-bg": p.page.hero_bg,
    background: p.page.hero_bg,
  } as Record<string, string>;
});

function onTextKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    sendTextMessage();
  }
}

function activeCastIndex(p: Program | undefined): number {
  if (!p?.cast.length) return 0;
  if (phase.value === "listening") return 1 % p.cast.length;
  if (phase.value === "speaking" || phase.value === "processing") return 0;
  return 0;
}

const pickerBuiltinLessons = computed(() =>
  lessons.value.filter((l) => l.is_builtin),
);
const pickerCustomLessons = computed(() =>
  lessons.value.filter((l) => !l.is_builtin),
);

const gradeStages = computed(() => {
  const order = ["幼儿园", "牛津阅读树", "小学"];
  const map = new Map<string, typeof grades.value>();
  for (const g of grades.value) {
    const label =
      g.stage_label || (g.stage === "kindergarten" ? "幼儿园" : "小学");
    const list = map.get(label) ?? [];
    list.push(g);
    map.set(label, list);
  }
  return order
    .filter((label) => map.has(label))
    .map((label) => ({ label, grades: map.get(label)! }));
});
</script>

<template>
  <div
    class="app"
    :class="[
      usesThemedShell ? `app--${skin}` : 'app--shell',
      screen === 'call' && ortActiveBook && 'app--ort-call',
    ]"
    :style="appStyle"
  >
    <nav v-if="screen !== 'call'" class="top-nav">
      <div class="top-nav__head">
        <div class="top-nav__brand-block">
          <p class="top-nav__brand">English Buddy</p>
          <p
            class="top-nav__online"
            :class="{ 'top-nav__online--live': activeCalls.connected > 0 }"
            :title="activeCallsDetail || undefined"
          >
            {{ activeCallsLabel }}
          </p>
        </div>
        <div class="top-nav__actions">
          <button
            type="button"
            class="top-nav__refresh"
            :disabled="refreshing"
            aria-label="强制刷新页面"
            @click="refreshApp"
          >
            {{ refreshing ? "…" : "刷新" }}
          </button>
          <div v-if="requireAuth" class="top-nav__user">
            <template v-if="isAuthenticated">
              <span>{{ displayName }}</span>
              <button
                type="button"
                class="top-nav__logout"
                @click="handleLogout()"
              >
                退出
              </button>
            </template>
            <button
              v-else
              type="button"
              class="top-nav__login"
              @click="openLogin('pick_show')"
            >
              登录
            </button>
          </div>
        </div>
      </div>
      <div class="top-nav__segment" role="tablist" aria-label="页面导航">
        <button
          type="button"
          role="tab"
          class="top-nav__seg-btn"
          :class="{
            'top-nav__seg-btn--active':
              screen === 'pick_show' ||
              (screen === 'login' && loginReturnTo === 'pick_show'),
          }"
          :aria-selected="
            screen === 'pick_show' ||
            (screen === 'login' && loginReturnTo === 'pick_show')
          "
          @click="goHome()"
        >
          首页
        </button>
        <button
          type="button"
          role="tab"
          class="top-nav__seg-btn"
          :class="{ 'top-nav__seg-btn--active': screen === 'ort_topic' }"
          :aria-selected="screen === 'ort_topic'"
          @click="goOrtTopic()"
        >
          牛津阅读树
        </button>
        <button
          type="button"
          role="tab"
          class="top-nav__seg-btn"
          :class="{
            'top-nav__seg-btn--active':
              screen === 'lesson_manage' ||
              (screen === 'login' && loginReturnTo === 'lesson_manage'),
          }"
          :aria-selected="
            screen === 'lesson_manage' ||
            (screen === 'login' && loginReturnTo === 'lesson_manage')
          "
          @click="goCustomLessons()"
        >
          自定义课文
        </button>
      </div>
    </nav>

    <!-- ① 首页选课文 -->
    <section v-if="screen === 'pick_show'" class="picker">
      <button type="button" class="picker__ort-banner" @click="goOrtTopic()">
        <span class="picker__ort-banner-title">牛津阅读树</span>
        <span class="picker__ort-banner-sub">
          {{ ortIllustratedCount }} 本配图带读 ·
          {{ sttEnabledForMe ? "可跟读" : "只听模式" }}
          <template v-if="ortIllustratedCount < 50">
            · 其余回首页选课文
          </template>
        </span>
      </button>
      <div class="picker__lesson-panel">
        <label class="picker__lesson-label">选老师</label>
        <div class="picker__teachers">
          <button
            v-for="p in programs"
            :key="p.id"
            type="button"
            class="teacher-chip"
            :class="[
              `teacher-chip--${p.page.skin}`,
              { 'teacher-chip--active': pickerProgramId === p.id },
            ]"
            @click="selectPickerProgram(p.id)"
          >
            <CharacterAvatar
              v-if="p.cast[0]"
              :stem="p.cast[0].avatar"
              :alt="p.cast[0].name_cn"
              size="md"
              class="teacher-chip__avatar"
            />
            <span class="teacher-chip__name">{{
              p.cast[0]?.name_cn ?? p.title
            }}</span>
          </button>
        </div>

        <label class="picker__lesson-label picker__lesson-label--sub" for="home-grade-select"
          >选年级</label
        >
        <select
          v-if="grades.length"
          id="home-grade-select"
          class="lesson-select"
          :value="pickerGradeId"
          :disabled="gradesLoading || lessonsLoading"
          @change="
            selectPickerGrade(($event.target as HTMLSelectElement).value)
          "
        >
          <template v-for="group in gradeStages" :key="group.label">
            <optgroup :label="group.label">
              <option v-for="g in group.grades" :key="g.id" :value="g.id">
                {{ g.title }}{{ g.subtitle ? ` · ${g.subtitle}` : "" }}
              </option>
            </optgroup>
          </template>
        </select>

        <label class="picker__lesson-label picker__lesson-label--sub" for="home-lesson-select"
          >选课文</label
        >
        <p v-if="gradesLoading || lessonsLoading" class="picker__lesson-loading">
          {{ gradesLoading ? "加载年级…" : "加载课文…" }}
        </p>
        <select
          v-else-if="lessons.length"
          id="home-lesson-select"
          class="lesson-select"
          :value="selectedLessonId ?? ''"
          @change="
            selectLessonOption(($event.target as HTMLSelectElement).value)
          "
        >
          <optgroup label="内置课文">
            <option
              v-for="lesson in pickerBuiltinLessons"
              :key="lesson.id"
              :value="lesson.id"
            >
              {{ lesson.title }}
            </option>
          </optgroup>
          <optgroup v-if="pickerCustomLessons.length" label="自定义课文">
            <option
              v-for="lesson in pickerCustomLessons"
              :key="lesson.id"
              :value="lesson.id"
            >
              {{ lesson.title
              }}{{
                prewarmStatusLabel(lesson)
                  ? `（${prewarmStatusLabel(lesson)}）`
                  : ""
              }}
            </option>
          </optgroup>
        </select>
        <p v-else-if="!gradesLoading && !lessonsLoading" class="picker__lesson-empty">
          <template
            v-if="
              builtinPrewarm &&
              !builtinPrewarm.complete &&
              (builtinPrewarm.waiting_lessons ?? 0) +
                (builtinPrewarm.pending_lessons ?? 0) >
                0
            "
          >
            内置课文预热中（{{ builtinPrewarm.ready_lessons ?? 0 }}/{{
              builtinPrewarm.total_lessons ?? 0
            }}
            课已就绪）· 未预热的课文不会显示，请稍后再选
          </template>
          <template v-else>该年级暂无已预热课文</template>
        </p>
        <p
          v-if="requireAuth && !isAuthenticated"
          class="picker__login-hint"
        >
          内置课文可直接带读。
          <button type="button" class="picker__login-link" @click="openLogin('pick_show')">
            登录
          </button>
          后可在「选课文」里选你的自定义课文
        </p>
        <p
          v-if="
            builtinPrewarm &&
            !builtinPrewarm.complete &&
            (builtinPrewarm.waiting_lessons ?? 0) > 0
          "
          class="picker__prewarm-hint"
        >
          后台预热进行中：{{ builtinPrewarm.ready_lessons ?? 0 }}/{{
            builtinPrewarm.total_lessons ?? 0
          }}
          课（当前老师 · 当前语速）
        </p>
        <p
          v-if="selectedLesson && !isBuiltinLesson(selectedLesson)"
          class="picker__lesson-status"
        >
          <span
            class="prewarm-badge"
            :class="{
              'prewarm-badge--ready': lessonReadyAtSpeed(
                selectedLesson,
                ttsSpeed,
              ),
            }"
          >
            {{ prewarmStatusLabel(selectedLesson) }}
          </span>
          <span v-if="!lessonReadyAtSpeed(selectedLesson, ttsSpeed)">
            · 自定义课文需预热后才能带读
          </span>
        </p>
        <label class="picker__lesson-label picker__lesson-label--sub">语速</label>
        <div class="speed-segment picker__speed" role="group" aria-label="语速">
          <button
            v-for="preset in ttsSpeedPresets"
            :key="preset.id"
            type="button"
            class="speed-segment__btn"
            :class="{ 'speed-segment__btn--active': ttsSpeedPreset === preset.id }"
            @click="setTtsSpeedPreset(preset.id)"
          >
            {{ preset.label }}
          </button>
        </div>
        <p v-if="catalogLoadError" class="picker__warn">
          {{ catalogLoadError }}
        </p>
        <p v-if="!ollamaOk && modelName" class="picker__warn">
          Ollama 未连接 — 请先启动 Ollama
        </p>
        <p v-if="readAlongFull" class="picker__warn">
          {{ readAlongLimitMessage }}
        </p>
        <p v-if="freeChatEnabledForMe && freeChatFull" class="picker__warn">
          {{ freeChatLimitMessage }}
        </p>
        <p v-if="!sttEnabledForMe && listenOnlyHint" class="picker__login-hint">
          {{ listenOnlyHint }}
        </p>
        <div class="picker__lesson-actions">
          <button
            type="button"
            class="picker__start-btn"
            :disabled="!canStartReadAlong"
            @click="enterShow()"
          >
            开始带读
          </button>
          <button
            v-if="freeChatEnabledForMe"
            type="button"
            class="picker__free-btn"
            :disabled="!canStartFreeChat || !ollamaOk"
            @click="enterFreeChat()"
          >
            自由聊天
          </button>
        </div>
        <p v-if="errorMessage" class="picker__error">{{ errorMessage }}</p>
      </div>
    </section>

    <!-- 牛津阅读树专题 -->
    <OrtTopicView
      v-else-if="screen === 'ort_topic'"
      :lesson-groups="ortFilteredLessonGroups"
      :lessons-loading="lessonsLoading || ortCatalogLoading"
      :catalog-error="ortCatalogError"
      :level-filter="ortLevelFilter"
      :selected-lesson-id="selectedLessonId"
      :selected-lesson="selectedLesson"
      :read-along-full="readAlongFull"
      :read-along-limit-message="readAlongLimitMessage"
      :can-start="canStartOrtReadAlong"
      :tts-speed-presets="ttsSpeedPresets"
      :tts-speed-preset="ttsSpeedPreset"
      :programs="programs"
      :picker-program-id="pickerProgramId"
      :prewarm-label="prewarmStatusLabel"
      :lesson-ready="ortLessonReadyForTopic"
      :illustrated-count="ortIllustratedCount"
      :listen-only-hint="listenOnlyHint"
      :start-button-label="ortStartButtonLabel"
      @set-level="setOrtLevelFilter"
      @select-lesson="selectOrtLesson"
      @select-program="selectPickerProgram"
      @set-speed="setTtsSpeedPreset"
      @start-read-along="startOrtReadAlong"
    />

    <!-- ② 登录（首页 / 自定义课文共用） -->
    <section v-else-if="screen === 'login'" class="login">
      <div class="login__card">
        <h2 class="login__title">登录</h2>
        <p class="login__lead">
          <template v-if="loginReturnTo === 'pick_show'">
            登录后可在首页「选课文」里选你的自定义课文，并开始带读
          </template>
          <template v-else>
            每位家庭成员各自管理自定义课文，互不影响
          </template>
        </p>
        <label class="setup__label" for="login-username">用户名</label>
        <input
          id="login-username"
          v-model="loginUsername"
          class="manage__input"
          type="text"
          maxlength="64"
          autocomplete="username"
        />
        <label class="setup__label setup__label--sub" for="login-password"
          >密码</label
        >
        <input
          id="login-password"
          v-model="loginPassword"
          class="manage__input"
          type="password"
          maxlength="128"
          autocomplete="current-password"
          @keydown.enter="submitLogin()"
        />
        <button
          type="button"
          class="manage__save-btn"
          :disabled="loginBusy || !loginUsername || !loginPassword"
          @click="submitLogin()"
        >
          登录
        </button>
        <p v-if="loginError" class="setup__error">{{ loginError }}</p>
        <button type="button" class="login__back" @click="goHome()">
          返回首页
        </button>
        <p v-if="!requireAuth" class="login__hint">
          服务端未配置账号（ENGLISH_BUDDY_USERS）
        </p>
      </div>
    </section>

    <!-- ③ 课文管理 + 预热 -->
    <section v-else-if="screen === 'lesson_manage'" class="manage">
      <div class="manage__notice" role="note">
        <p class="manage__notice-title">为什么要预热？</p>
        <p class="manage__notice-text">
          自定义课文需要先把每句话转成<strong>老师语音</strong>并缓存好，带读时才能立刻播放，不会卡顿或等很久。
        </p>
        <p class="manage__notice-text">
          须按上方选的<strong>老师 + 语速</strong>分别预热；换老师或改语速后，请再点一次「预热语音」。显示「已预热」后，回首页即可带读。
        </p>
      </div>

      <div class="manage__teachers">
        <span class="manage__section-label">预热老师</span>
        <div class="picker__teachers picker__teachers--inline">
          <button
            v-for="p in programs"
            :key="p.id"
            type="button"
            class="teacher-chip teacher-chip--compact"
            :class="[
              `teacher-chip--${p.page.skin}`,
              { 'teacher-chip--active': manageProgramId === p.id },
            ]"
            @click="switchManageProgram(p.id)"
          >
            <CharacterAvatar
              v-if="p.cast[0]"
              :stem="p.cast[0].avatar"
              :alt="p.cast[0].name_cn"
              size="sm"
              class="teacher-chip__avatar"
            />
            <span class="teacher-chip__name">{{
              p.cast[0]?.name_cn ?? p.title
            }}</span>
          </button>
        </div>
      </div>

      <div class="manage__speed">
        <span class="speed-field__label">预热语速</span>
        <div class="speed-segment" role="group" aria-label="预热语速">
          <button
            v-for="preset in ttsSpeedPresets"
            :key="preset.id"
            type="button"
            class="speed-segment__btn"
            :class="{ 'speed-segment__btn--active': ttsSpeedPreset === preset.id }"
            @click="setTtsSpeedPreset(preset.id)"
          >
            {{ preset.label }}
          </button>
        </div>
      </div>

      <div class="manage__card">
        <h2 class="manage__subtitle">添加自定义课文</h2>
        <label class="setup__label" for="new-lesson-title">课文名称</label>
        <input
          id="new-lesson-title"
          v-model="newLessonTitle"
          class="manage__input"
          type="text"
          maxlength="80"
          placeholder="例如：第11课 · 周末公园"
        />
        <label class="setup__label setup__label--sub" for="new-lesson-text"
          >课文内容（每行一句）</label
        >
        <textarea
          id="new-lesson-text"
          v-model="newLessonText"
          class="setup__textarea"
          rows="4"
          placeholder="每行一句英文，每句不超过 10 个词"
        />
        <button
          type="button"
          class="manage__save-btn"
          :disabled="lessonManageBusy"
          @click="submitCustomLesson"
        >
          保存课文
        </button>
      </div>

      <div class="manage__list">
        <h2 class="manage__subtitle">我的课文（语速 {{ ttsSpeed }}×）</h2>
        <p class="manage__hint">
          保存后先点「预热语音」，状态变为「已预热」才能在首页带读。内置课文无需此步骤。
        </p>
        <ul v-if="customLessons.length" class="manage__items">
          <li
            v-for="lesson in customLessons"
            :key="lesson.id"
            class="manage__item"
          >
            <div class="manage__item-head">
              <div class="manage__item-title">
                <strong>{{ lesson.title }}</strong>
                <span
                  class="prewarm-badge"
                  :class="{
                    'prewarm-badge--ready': lessonReadyAtSpeed(
                      lesson,
                      ttsSpeed,
                    ),
                  }"
                >
                  {{ prewarmStatusLabel(lesson) }}
                </span>
              </div>
              <button
                type="button"
                class="manage__delete-btn"
                aria-label="删除课文"
                :disabled="lessonManageBusy"
                @click="removeCustomLesson(lesson.id)"
              >
                <AppIcon name="trash" />
              </button>
            </div>
            <button
              type="button"
              class="manage__warm-btn"
              :disabled="lessonManageBusy"
              @click="runLessonPrewarm(lesson.id)"
            >
              {{
                lessonReadyAtSpeed(lesson, ttsSpeed)
                  ? "重新预热"
                  : "预热语音"
              }}
            </button>
          </li>
        </ul>
        <p v-else class="manage__empty">还没有自定义课文</p>
      </div>

      <p v-if="lessonManageError" class="setup__error">{{ lessonManageError }}</p>
    </section>

    <!-- ③ 通话中 -->
    <section
      v-else-if="screen === 'call'"
      class="call-screen"
      :class="{ 'call-screen--ort': callMode === 'read_along' && ortActiveBook }"
    >
      <header class="call-screen__top call-screen__top--call">
        <button
          type="button"
          class="btn-refresh-call"
          :disabled="refreshing"
          aria-label="强制刷新页面"
          @click="refreshFromCall"
        >
          {{ refreshing ? "…" : "刷新" }}
        </button>
        <div class="call-screen__top-meta">
          <p class="call-screen__mode">
            {{ activeProgramTitle || selectedProgram?.title }}
            · {{ callMode === "read_along" ? "带读" : "聊天" }}
          </p>
          <p
            class="call-screen__online"
            :class="{ 'call-screen__online--live': activeCalls.connected > 0 }"
            :title="activeCallsDetail || undefined"
          >
            {{ activeCallsLabel }}
          </p>
        </div>
        <button
          type="button"
          class="btn-hangup"
          aria-label="挂断带读"
          @click="endCall"
        >
          <AppIcon name="hangup" />
          <span>挂断</span>
        </button>
      </header>

      <div class="call-screen__body">
        <main
          class="call-screen__main"
          :class="{
            'call-screen__main--read': callMode === 'read_along',
            'call-screen__main--ort': callMode === 'read_along' && ortActiveBook,
          }"
        >
          <div
            v-if="!(callMode === 'read_along' && ortActiveBook)"
            :class="[orbClass, callMode === 'read_along' && 'orb--compact']"
            aria-hidden="true"
          >
            <span class="orb__ring orb__ring--1" />
            <span class="orb__ring orb__ring--2" />
            <CharacterAvatar
              v-if="selectedProgram?.cast[activeCastIndex(selectedProgram)]"
              :stem="
                selectedProgram.cast[activeCastIndex(selectedProgram)].avatar
              "
              :alt="
                selectedProgram.cast[activeCastIndex(selectedProgram)].name_cn
              "
              :size="callMode === 'read_along' ? 'md' : 'xl'"
              class="orb__avatar"
            />
          </div>

          <p v-if="micWarning" class="call-screen__mic-warn" role="status">
            {{ micWarning }}
          </p>

          <div
            v-if="callMode === 'read_along'"
            class="speed-field speed-field--call"
          >
            <span class="speed-field__label">语速</span>
            <div class="speed-segment speed-segment--call" role="group" aria-label="语速">
              <button
                v-for="preset in ttsSpeedPresets"
                :key="preset.id"
                type="button"
                class="speed-segment__btn"
                :class="{ 'speed-segment__btn--active': ttsSpeedPreset === preset.id }"
                @click="setTtsSpeedPreset(preset.id)"
              >
                {{ preset.label }}
              </button>
            </div>
          </div>

          <div
            v-if="callMode === 'read_along' && ortActiveBook"
            class="ort-call-page"
          >
            <div
              class="ort-call-page__frame"
              :class="{ 'ort-call-page__frame--missing': ortCallPageMissing }"
              @touchstart.passive="onOrtPageTouchStart"
              @touchend.passive="onOrtPageTouchEnd"
            >
              <img
                class="ort-call-page__img"
                :src="ortCallPageImage"
                :alt="`${ortActiveBook.title} 第 ${readAlongPageIndex + 1} 页`"
                decoding="async"
                @error="onOrtImgError"
              />
              <button
                type="button"
                class="ort-call-page__nav ort-call-page__nav--prev"
                :disabled="!canOrtPrevPage"
                aria-label="上一页"
                @click="ortGoToPrevPage"
              >
                <AppIcon name="prev" />
              </button>
              <button
                type="button"
                class="ort-call-page__nav ort-call-page__nav--next"
                :disabled="!canOrtNextPage"
                aria-label="下一页"
                @click="ortGoToNextPage"
              >
                <AppIcon name="next" />
              </button>
              <p
                v-if="ortCallPageMissing"
                class="ort-call-page__missing-label"
              >
                暂无页图
              </p>
            </div>
            <p class="ort-call-page__meta">
              第 {{ readAlongPageIndex + 1 }} / {{ ortActiveBook.page_count }} 页 · 左右滑动翻页
            </p>
          </div>

          <div
            v-if="
              callMode === 'read_along' &&
              (ortScriptLines?.length || materialLines.length)
            "
            class="script-panel"
            :class="{ 'script-panel--ort': ortActiveBook }"
          >
            <p class="script-panel__label">
              <template v-if="ortActiveBook">本页句子</template>
              <template v-else>课文（点一句可重读）</template>
              <span
                v-if="pronunciationAssess && sttEnabled"
                class="script-panel__legend"
              >
                · 绿过关 · 黄接近 · 橙可重读
              </span>
            </p>
            <ul class="script-panel__lines">
              <template v-if="ortScriptLines">
                <li
                  v-for="row in ortScriptLines"
                  :key="row.globalIndex"
                  class="script-panel__line"
                  :class="{
                    'script-panel__line--active':
                      row.globalIndex === readAlongLineIndex &&
                      !lineVerdict(row.globalIndex),
                    'script-panel__line--done':
                      row.globalIndex < readAlongLineIndex &&
                      !lineVerdict(row.globalIndex) &&
                      readAlongTurn !== 'done',
                    'script-panel__line--pass':
                      lineVerdict(row.globalIndex) === 'pass',
                    'script-panel__line--almost':
                      lineVerdict(row.globalIndex) === 'almost',
                    'script-panel__line--retry':
                      lineVerdict(row.globalIndex) === 'retry',
                    'script-panel__line--clickable': canRereadLine,
                  }"
                  role="button"
                  :tabindex="canRereadLine ? 0 : -1"
                  :aria-disabled="!canRereadLine"
                  @click="rereadLine(row.globalIndex)"
                  @keydown.enter.prevent="rereadLine(row.globalIndex)"
                >
                  {{ row.text }}
                </li>
              </template>
              <template v-else>
                <li
                  v-for="(line, i) in materialLines"
                  :key="i"
                  class="script-panel__line"
                  :class="{
                    'script-panel__line--active':
                      i === readAlongLineIndex && !lineVerdict(i),
                    'script-panel__line--done':
                      i < readAlongLineIndex &&
                      !lineVerdict(i) &&
                      readAlongTurn !== 'done',
                    'script-panel__line--pass': lineVerdict(i) === 'pass',
                    'script-panel__line--almost': lineVerdict(i) === 'almost',
                    'script-panel__line--retry': lineVerdict(i) === 'retry',
                    'script-panel__line--clickable': canRereadLine,
                  }"
                  role="button"
                  :tabindex="canRereadLine ? 0 : -1"
                  :aria-disabled="!canRereadLine"
                  @click="rereadLine(i)"
                  @keydown.enter.prevent="rereadLine(i)"
                >
                  {{ line }}
                </li>
              </template>
            </ul>
          </div>

          <div
            v-if="readAlongTurn"
            :key="turnCueKey"
            class="turn-strip"
            :class="`turn-strip--${readAlongTurn}`"
            role="status"
            aria-live="polite"
          >
            <span class="turn-strip__dot" aria-hidden="true" />
            <span v-if="readAlongTurn === 'teacher'" class="turn-strip__text">{{
              teacherPaused
                ? "已暂停 · 点继续"
                : sttEnabled
                  ? "听老师说"
                  : "只听 · 听老师说"
            }}</span>
            <span v-else-if="readAlongTurn === 'child'" class="turn-strip__text"
              >小朋友说 · 叮叮</span
            >
            <span v-else-if="readAlongTurn === 'busy'" class="turn-strip__text"
              >{{ statusText || "等一下" }}</span
            >
            <span v-else-if="readAlongTurn === 'done'" class="turn-strip__text"
              >{{ rereadFromDone ? "重读这一句…" : "读完啦 · 点句子重读" }}</span
            >
            <div
              v-if="readAlongTurn === 'child'"
              class="turn-strip__waves"
              aria-hidden="true"
            >
              <span /><span /><span />
            </div>
          </div>
          <div
            v-if="showReadActionBar"
            class="call-screen__read-actions"
            role="group"
            aria-label="带读操作"
          >
            <button
              type="button"
              class="btn-read-action btn-read-action--prev"
              :disabled="!canBackToPreviousLine"
              @click="backToPreviousLine"
            >
              <AppIcon name="prev" />
              <span>上一句</span>
            </button>
            <button
              type="button"
              class="btn-read-action btn-read-action--repeat"
              :disabled="!canRepeatCurrentLine"
              @click="repeatCurrentLine"
            >
              <AppIcon name="repeat" />
              <span>{{ readAlongTurn === "done" ? "重读这句" : "再说一遍" }}</span>
            </button>
            <button
              v-if="ortActiveBook"
              type="button"
              class="btn-read-action btn-read-action--pause"
              :disabled="!canToggleOrtPause"
              :aria-pressed="teacherPaused"
              @click="toggleOrtTeacherPause"
            >
              <AppIcon :name="teacherPaused ? 'play' : 'pause'" />
              <span>{{ teacherPaused ? "继续" : "暂停" }}</span>
            </button>
            <button
              v-if="sttEnabled"
              type="button"
              class="btn-read-action btn-read-action--done"
              :disabled="readAlongTurn !== 'child' || !canTapChildDone"
              @click="tapChildDone"
            >
              <AppIcon name="check" />
              <span>我说完啦</span>
            </button>
            <button
              v-if="ortActiveBook"
              type="button"
              class="btn-read-action btn-read-action--next"
              :disabled="!canOrtAdvanceLine"
              @click="ortAdvanceLine"
            >
              <AppIcon name="next" />
              <span>下一句</span>
            </button>
          </div>
          <p
            v-if="callMode === 'read_along' && readAlongTurn && readAlongTurn !== 'done' && sttEnabled"
            class="call-screen__read-intro"
          >
            听「叮叮」后跟读；可暂停 / 上一句 / 再说一遍 / 我说完啦 / 下一句
          </p>
          <p
            v-if="
              callMode === 'read_along' &&
              ortActiveBook &&
              readAlongTurn &&
              readAlongTurn !== 'done' &&
              !sttEnabled
            "
            class="call-screen__read-intro"
          >
            只听模式：老师逐句朗读；可暂停；翻页或上一句后需点「下一句」继续
          </p>
          <p v-if="!readAlongTurn" class="call-screen__status">
            {{
              callMode === "free"
                ? statusText
                : phase === "connecting"
                  ? statusText.includes("Whisper") || statusText.includes("加载")
                    ? "正在准备语音识别…"
                    : statusText.includes("老师") ||
                        statusText.includes("带读") ||
                        statusText.includes("课文")
                      ? statusText
                      : "正在接通带读…"
                  : statusText
            }}
          </p>

          <p
            v-if="interimText && inCall && callMode !== 'read_along'"
            class="call-screen__interim"
          >
            {{ interimText }}
          </p>
          <div
            v-if="lastAssistant && inCall && callMode !== 'read_along'"
            class="call-screen__assistant"
            role="status"
          >
            <span class="call-screen__assistant-label">老师说</span>
            <p class="call-screen__assistant-text">{{ lastAssistant }}</p>
          </div>
          <p v-if="errorMessage && phase === 'error'" class="call-screen__error">
            {{ errorMessage }}
          </p>
        </main>
      </div>

      <div v-if="callMode !== 'read_along'" class="call-screen__dock">
        <button
          v-if="canInterruptTeacher"
          type="button"
          class="btn btn--interrupt"
          @click="interruptTeacher"
        >
          我要说话
        </button>

        <div class="call-screen__textbar">
          <input
            v-model="typedMessage"
            type="text"
            class="call-screen__input"
            placeholder="打字回复"
            enterkeyhint="send"
            autocomplete="off"
            :disabled="phase === 'connecting'"
            @keydown="onTextKeydown"
          />
          <button
            type="button"
            class="btn btn--send"
            :disabled="!typedMessage.trim() || phase === 'connecting'"
            @click="sendTextMessage"
          >
            发送
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.app {
  min-height: 100%;
  min-height: 100dvh;
  color: #475569;
  transition: background 0.35s ease;
}

/* —— Picker —— */
.top-nav {
  position: sticky;
  top: 0;
  z-index: 20;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: 0.5rem;
  max-width: 28rem;
  margin: 0 auto;
  width: 100%;
  padding: max(env(safe-area-inset-top), 0.5rem) 1rem 0.65rem;
  background: rgba(255, 255, 255, 0.94);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-bottom: 1px solid rgba(226, 232, 240, 0.85);
  box-shadow: 0 4px 18px rgba(148, 163, 184, 0.1);
}

.top-nav__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
}

.top-nav__brand-block {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  min-width: 0;
}

.top-nav__brand {
  margin: 0;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.04em;
  color: #6366f1;
}

.top-nav__online {
  margin: 0;
  font-size: 0.68rem;
  font-weight: 700;
  color: #94a3b8;
  line-height: 1.2;
}

.top-nav__online--live {
  color: #059669;
}

.top-nav__actions {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  flex-shrink: 0;
}

.top-nav__refresh {
  border: 1px solid #e2e8f0;
  background: #fff;
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.3rem 0.55rem;
  border-radius: 0.5rem;
  min-height: 1.85rem;
  cursor: pointer;
}

.top-nav__refresh:disabled {
  opacity: 0.6;
  cursor: wait;
}

.top-nav__user {
  display: flex;
  align-items: center;
  gap: 0.45rem;
  font-size: 0.75rem;
  font-weight: 700;
  color: #64748b;
}

.top-nav__logout,
.top-nav__login {
  border: none;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 0.72rem;
  font-weight: 800;
  padding: 0.3rem 0.55rem;
  border-radius: 0.5rem;
}

.picker__prewarm-hint {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #b45309;
  line-height: 1.45;
}

.picker__login-hint {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.45;
}

.picker__login-link {
  border: none;
  background: none;
  color: #4f46e5;
  font-size: inherit;
  font-weight: 800;
  padding: 0;
  text-decoration: underline;
  cursor: pointer;
}

.login {
  max-width: 28rem;
  margin: 0 auto;
  padding: 1rem;
  min-height: calc(100dvh - 5.5rem);
  background: #f8fafc;
}

.login__card {
  margin-top: 0.5rem;
  padding: 1rem;
  border-radius: 1rem;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 24px rgba(148, 163, 184, 0.14);
}

.login__title {
  font-size: 1.1rem;
  font-weight: 800;
  color: #334155;
  margin-bottom: 0.35rem;
}

.login__lead {
  font-size: 0.82rem;
  color: #64748b;
  line-height: 1.45;
  margin-bottom: 0.85rem;
}

.login__hint {
  margin-top: 0.65rem;
  font-size: 0.78rem;
  color: #94a3b8;
}

.login__back {
  display: block;
  width: 100%;
  margin-top: 0.65rem;
  border: none;
  background: transparent;
  color: #64748b;
  font-size: 0.82rem;
  font-weight: 700;
  padding: 0.45rem 0;
  cursor: pointer;
}

.top-nav__segment {
  display: flex;
  width: 100%;
  padding: 0.28rem;
  border-radius: 0.85rem;
  background: #eef2ff;
  gap: 0.22rem;
}

.top-nav__seg-btn {
  flex: 1;
  min-height: 2.5rem;
  padding: 0.5rem 0.65rem;
  border: none;
  border-radius: 0.62rem;
  background: transparent;
  font-size: 0.88rem;
  font-weight: 800;
  color: #64748b;
  transition:
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s,
    transform 0.12s;
}

.top-nav__seg-btn--active {
  background: #fff;
  color: #4f46e5;
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.14);
}

.top-nav__seg-btn:active:not(:disabled) {
  transform: scale(0.98);
}

.picker__ort-banner {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.15rem;
  width: 100%;
  margin-bottom: 0.85rem;
  padding: 0.85rem 1rem;
  border: 1px solid #c8dcc7;
  border-radius: 14px;
  background: linear-gradient(135deg, #f4faf3 0%, #eef5ed 100%);
  cursor: pointer;
  text-align: left;
}

.picker__ort-banner-title {
  font-size: 1rem;
  font-weight: 700;
  color: #3d5c3c;
}

.picker__ort-banner-sub {
  font-size: 0.78rem;
  color: #6b8a6a;
}

.picker {
  max-width: 28rem;
  margin: 0 auto;
  padding: 0.65rem 1rem max(env(safe-area-inset-bottom), 1.5rem);
  min-height: calc(100dvh - 5.5rem);
  background: linear-gradient(165deg, #fff8fb 0%, #f0f9ff 50%, #fffbeb 100%);
}

.picker__lesson-panel {
  margin-top: 0;
  padding: 1rem;
  border-radius: 1.1rem;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 8px 24px rgba(148, 163, 184, 0.14);
}

.picker__lesson-label {
  display: block;
  font-size: 0.88rem;
  font-weight: 800;
  margin-bottom: 0.45rem;
}

.picker__lesson-label--sub {
  margin-top: 0.75rem;
}

.picker__teachers {
  display: flex;
  gap: 0.65rem;
  margin-bottom: 0.15rem;
}

.picker__teachers--inline {
  margin-bottom: 0;
}

.teacher-chip {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  padding: 0.65rem 0.5rem;
  border-radius: 0.9rem;
  border: 2px solid #e2e8f0;
  background: #fff;
  transition:
    border-color 0.15s,
    box-shadow 0.15s,
    transform 0.15s;
}

.teacher-chip:active {
  transform: scale(0.98);
}

.teacher-chip--girls.teacher-chip--active {
  border-color: #f472b6;
  box-shadow: 0 0 0 3px rgba(244, 114, 182, 0.18);
}

.teacher-chip--boys.teacher-chip--active {
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.18);
}

.teacher-chip--compact {
  flex: 0 1 auto;
  min-width: 5.5rem;
  padding: 0.5rem 0.65rem;
  gap: 0.25rem;
}

.teacher-chip__name {
  font-size: 0.88rem;
  font-weight: 800;
  color: #334155;
  line-height: 1.2;
}

.teacher-chip--compact .teacher-chip__name {
  font-size: 0.8rem;
}

.picker__lesson-empty,
.picker__lesson-loading {
  font-size: 0.85rem;
  color: #64748b;
}

.picker__lesson-status {
  margin-top: 0.5rem;
  font-size: 0.8rem;
  color: #64748b;
}

.picker__speed {
  margin-top: 0.15rem;
  margin-bottom: 0.55rem;
}

.picker__warn {
  margin-bottom: 0.55rem;
  font-size: 0.82rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  background: #fffbeb;
  color: #b45309;
}

.picker__lesson-actions {
  margin-top: 0.35rem;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.picker__free-btn {
  width: 100%;
  min-height: 2.75rem;
  padding: 0.72rem 1rem;
  border: 2px solid #c7d2fe;
  border-radius: 0.85rem;
  font-size: 0.95rem;
  font-weight: 800;
  color: #4338ca;
  background: #eef2ff;
}

.picker__free-btn:disabled {
  opacity: 0.5;
}

.picker__start-btn {
  width: 100%;
  min-height: 2.95rem;
  padding: 0.8rem 1rem;
  border: none;
  border-radius: 0.85rem;
  font-size: 1rem;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.28);
}

.picker__start-btn:disabled {
  opacity: 0.5;
  box-shadow: none;
}

.picker__error {
  margin-top: 0.5rem;
  font-size: 0.82rem;
  color: #e11d48;
  font-weight: 600;
}

.prewarm-badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 800;
  background: #f1f5f9;
  color: #64748b;
}

.prewarm-badge--ready {
  background: #ecfdf5;
  color: #047857;
}

.btn--sm {
  min-height: 2.5rem;
  padding: 0.55rem 0.75rem;
  font-size: 0.88rem;
}

.manage {
  max-width: 28rem;
  margin: 0 auto;
  padding: 0.5rem 1rem max(env(safe-area-inset-bottom), 1.5rem);
  min-height: calc(100dvh - 5.5rem);
  background: #f8fafc;
}

.manage__speed {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-bottom: 0.75rem;
}

.manage__section-label {
  width: 100%;
  font-size: 0.78rem;
  font-weight: 800;
  color: #64748b;
  margin-bottom: 0.35rem;
}

.manage__teachers,
.manage__grades {
  margin-bottom: 0.65rem;
}

.manage__grades .manage__grade-tab {
  margin-right: 0.4rem;
  margin-bottom: 0.4rem;
}

.manage__grades {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
}

.manage__stage {
  width: 100%;
  margin-top: 0.25rem;
  font-size: 0.72rem;
  font-weight: 800;
  color: #94a3b8;
}

.manage__stage:first-of-type {
  margin-top: 0;
}

.manage__grade-tab {
  min-height: 2.2rem;
  padding: 0 0.75rem;
  border-radius: 999px;
  border: 2px solid #e2e8f0;
  background: #fff;
  font-size: 0.8rem;
  font-weight: 800;
  color: #64748b;
}

.manage__grade-tab--active {
  border-color: #6366f1;
  color: #6366f1;
  background: #eef2ff;
}

.manage__teachers {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.4rem;
}

.manage__card,
.manage__list {
  background: rgba(255, 255, 255, 0.92);
  border-radius: 1rem;
  padding: 0.9rem;
  margin-bottom: 0.75rem;
  box-shadow: 0 6px 20px rgba(148, 163, 184, 0.1);
}

.manage__subtitle {
  font-size: 0.95rem;
  font-weight: 800;
  margin-bottom: 0.55rem;
}

.manage__input {
  width: 100%;
  min-height: 2.6rem;
  margin-bottom: 0.55rem;
  padding: 0.55rem 0.8rem;
  border-radius: 0.75rem;
  border: 2px solid #e2e8f0;
  font-size: 0.95rem;
}

.manage__notice {
  margin-bottom: 0.75rem;
  padding: 0.75rem 0.85rem;
  border-radius: 0.85rem;
  background: #eff6ff;
  border: 1px solid #bfdbfe;
}

.manage__notice-title {
  margin: 0 0 0.35rem;
  font-size: 0.82rem;
  font-weight: 800;
  color: #1d4ed8;
}

.manage__notice-text {
  margin: 0 0 0.35rem;
  font-size: 0.78rem;
  line-height: 1.5;
  color: #475569;
}

.manage__notice-text:last-child {
  margin-bottom: 0;
}

.manage__notice-text strong {
  color: #334155;
  font-weight: 800;
}

.manage__hint {
  font-size: 0.78rem;
  color: #64748b;
  line-height: 1.45;
  margin-bottom: 0.55rem;
}

.manage__items {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.55rem;
}

.manage__item {
  padding: 0.65rem 0.7rem;
  border-radius: 0.75rem;
  border: 1px solid #e2e8f0;
  background: #fff;
}

.manage__save-btn {
  width: 100%;
  margin-top: 0.65rem;
  min-height: 2.85rem;
  padding: 0.75rem 1rem;
  border: none;
  border-radius: 0.85rem;
  font-size: 0.95rem;
  font-weight: 800;
  color: #fff;
  background: linear-gradient(135deg, #6366f1, #8b5cf6);
  box-shadow: 0 8px 20px rgba(99, 102, 241, 0.28);
}

.manage__save-btn:disabled {
  opacity: 0.5;
  box-shadow: none;
}

.manage__item-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 0.5rem;
  margin-bottom: 0.55rem;
}

.manage__item-title {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 0.3rem;
  min-width: 0;
}

.manage__item-head strong {
  font-size: 0.9rem;
  line-height: 1.35;
}

.manage__delete-btn {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 2.35rem;
  height: 2.35rem;
  border: none;
  border-radius: 0.65rem;
  color: #dc2626;
  background: #fef2f2;
}

.manage__delete-btn:active:not(:disabled) {
  background: #fee2e2;
}

.manage__delete-btn:disabled {
  opacity: 0.45;
}

.manage__warm-btn {
  width: 100%;
  min-height: 2.5rem;
  padding: 0.6rem 0.85rem;
  border-radius: 0.75rem;
  border: 2px solid #c7d2fe;
  background: #eef2ff;
  color: #4f46e5;
  font-size: 0.88rem;
  font-weight: 800;
}

.manage__warm-btn:disabled {
  opacity: 0.5;
}

.manage__empty {
  font-size: 0.85rem;
  color: #94a3b8;
}

/* —— Form fields (自定义课文) —— */
.setup__label {
  display: block;
  font-size: 0.88rem;
  font-weight: 800;
  margin-bottom: 0.5rem;
}

.setup__label--sub {
  margin-top: 0.75rem;
  font-size: 0.8rem;
  color: #64748b;
}

.lesson-select {
  width: 100%;
  min-height: 2.85rem;
  margin-bottom: 0.35rem;
  padding: 0.55rem 2.25rem 0.55rem 0.85rem;
  border-radius: 0.85rem;
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 28%, #fff);
  background-color: #fff;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8'%3E%3Cpath fill='%2364748b' d='M1.4 1.4 6 6l4.6-4.6L12 3.4 6 9.4 0 3.4z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 0.85rem center;
  background-size: 0.65rem;
  font-size: 0.92rem;
  font-weight: 700;
  color: #334155;
  appearance: none;
  -webkit-appearance: none;
}

.lesson-select:focus {
  outline: none;
  border-color: var(--accent, #6366f1);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent, #6366f1) 20%, transparent);
}

.setup__textarea {
  width: 100%;
  min-height: 7.5rem;
  max-height: 40vh;
  padding: 0.85rem;
  border-radius: 0.85rem;
  border: 2px dashed rgba(148, 163, 184, 0.45);
  background: #fff;
  font-size: 1rem;
  line-height: 1.5;
  resize: none;
}

.setup__textarea:focus {
  outline: none;
  border-style: solid;
  border-color: var(--accent, #6366f1);
  box-shadow: 0 0 0 3px color-mix(in srgb, var(--accent, #6366f1) 20%, transparent);
}

.btn {
  min-height: 3rem;
  padding: 0.85rem 1rem;
  border-radius: 999px;
  font-size: 1rem;
  font-weight: 800;
  text-align: center;
}

.btn--primary {
  background: var(--btn-primary, linear-gradient(135deg, #6366f1, #8b5cf6));
  color: #fff;
  box-shadow: 0 8px 22px var(--btn-shadow, rgba(99, 102, 241, 0.3));
}

.btn--primary:disabled {
  opacity: 0.5;
  box-shadow: none;
}

.btn--ghost {
  background: rgba(255, 255, 255, 0.92);
  color: var(--accent, #6366f1);
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 35%, #fff);
}

.setup__error {
  font-size: 0.82rem;
  padding: 0.5rem 0.75rem;
  border-radius: 0.75rem;
  background: #fff1f2;
  color: #e11d48;
  font-weight: 600;
}

/* —— Call —— */
.call-screen {
  max-width: 28rem;
  margin: 0 auto;
  width: 100%;
  min-height: 100dvh;
  display: flex;
  flex-direction: column;
  padding: max(env(safe-area-inset-top), 0.5rem) 0.85rem 0;
}

.call-screen__top {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  padding-bottom: 0.35rem;
}

.call-screen__top-meta {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.2rem;
  min-width: 0;
  text-align: center;
}

.call-screen__online {
  margin: 0;
  font-size: 0.68rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.72);
}

.call-screen__online--live {
  color: #bbf7d0;
}

.call-screen__top--call {
  position: relative;
  padding-right: 4.75rem;
  padding-left: 4.75rem;
  min-height: 2.65rem;
}

.call-screen__mode {
  font-size: 0.75rem;
  font-weight: 800;
  color: #64748b;
  text-align: center;
  line-height: 1.3;
}

.btn-refresh-call {
  position: absolute;
  left: 0;
  top: 50%;
  transform: translateY(-50%);
  border: 1px solid rgba(255, 255, 255, 0.35);
  background: rgba(255, 255, 255, 0.92);
  color: #64748b;
  font-size: 0.72rem;
  font-weight: 800;
  min-height: 2.1rem;
  padding: 0.35rem 0.65rem;
  border-radius: 999px;
  cursor: pointer;
}

.btn-refresh-call:disabled {
  opacity: 0.6;
  cursor: wait;
}

.btn-refresh-call:active:not(:disabled) {
  transform: translateY(-50%) scale(0.97);
}

.btn-hangup {
  position: absolute;
  right: 0;
  top: 50%;
  transform: translateY(-50%);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.3rem;
  min-height: 2.35rem;
  padding: 0.4rem 0.7rem;
  border-radius: 999px;
  border: none;
  color: #fff;
  font-size: 0.78rem;
  font-weight: 800;
  letter-spacing: 0.02em;
  background: linear-gradient(145deg, #ef4444, #dc2626);
  box-shadow: 0 4px 16px rgba(220, 38, 38, 0.38);
}

.btn-hangup:active {
  transform: translateY(-50%) scale(0.97);
}

.btn-hangup .app-icon--hangup {
  width: 0.95rem;
  height: 0.95rem;
  transform: rotate(135deg);
}

.btn--with-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 0.45rem;
}

.call-screen__body {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  overscroll-behavior: contain;
}

.call-screen__main {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: flex-start;
  gap: 0.65rem;
  padding: 0.25rem 0.25rem 0.5rem;
  min-height: 0;
}

.orb {
  position: relative;
  flex-shrink: 0;
  width: clamp(7.5rem, 42vw, 9.5rem);
  height: clamp(7.5rem, 42vw, 9.5rem);
  display: flex;
  align-items: center;
  justify-content: center;
}

.orb__avatar {
  z-index: 2;
  flex-shrink: 0;
}

.orb__ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 3px solid color-mix(in srgb, var(--accent, #6366f1) 40%, #fff);
  background: rgba(255, 255, 255, 0.4);
}

.orb--listen .orb__ring--1 {
  animation: pulse 1.6s ease-out infinite;
}
.orb--listen .orb__ring--2 {
  animation: pulse 1.6s ease-out 0.5s infinite;
}
.orb--think .orb__avatar {
  animation: think 1.2s ease-in-out infinite;
}
.orb--speak .orb__ring--1 {
  animation: speak 0.5s ease-in-out infinite alternate;
}
.orb--connect .orb__ring--1 {
  animation: spin 2s linear infinite;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-7px);
  }
}
@keyframes pulse {
  0% {
    transform: scale(0.88);
    opacity: 0.95;
  }
  100% {
    transform: scale(1.28);
    opacity: 0;
  }
}
@keyframes think {
  0%,
  100% {
    transform: scale(0.94) rotate(-2deg);
  }
  50% {
    transform: scale(1.05) rotate(2deg);
  }
}
@keyframes speak {
  from {
    transform: scale(1);
  }
  to {
    transform: scale(1.06);
  }
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.call-screen__main--read {
  justify-content: flex-start;
  gap: 0.55rem;
  padding-top: 0.15rem;
}

.call-screen--ort {
  padding-left: 0;
  padding-right: 0;
}

.call-screen--ort .call-screen__top {
  padding-left: 0.85rem;
  padding-right: 0.85rem;
}

.call-screen__main--ort {
  align-items: stretch;
  gap: 0.35rem;
  padding-left: 0;
  padding-right: 0;
  width: 100%;
}

.orb--compact {
  width: clamp(5.5rem, 28vw, 6.5rem);
  height: clamp(5.5rem, 28vw, 6.5rem);
  margin-bottom: 0.15rem;
}

.ort-call-page {
  margin: 0.25rem 0 0.35rem;
  text-align: center;
  width: 100%;
}

.call-screen__main--ort .ort-call-page {
  flex: 0 0 auto;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: flex-start;
  margin: 0;
}

.ort-call-page__frame {
  position: relative;
  width: 100%;
  aspect-ratio: 986 / 1136;
  max-height: min(58dvh, calc(100vw * 1136 / 986));
  margin: 0 auto;
  background: #f0ebe3;
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
  touch-action: pan-y;
}

.ort-call-page__nav {
  position: absolute;
  top: 50%;
  z-index: 2;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 2.75rem;
  height: 2.75rem;
  padding: 0;
  border: none;
  border-radius: 999px;
  color: #3d3428;
  background: rgba(255, 255, 255, 0.82);
  box-shadow: 0 2px 10px rgba(45, 38, 28, 0.14);
  transform: translateY(-50%);
  cursor: pointer;
  -webkit-tap-highlight-color: transparent;
}

.ort-call-page__nav:disabled {
  opacity: 0.28;
  cursor: default;
}

.ort-call-page__nav--prev {
  left: 0.45rem;
}

.ort-call-page__nav--next {
  right: 0.45rem;
}

.ort-call-page__nav:not(:disabled):active {
  transform: translateY(-50%) scale(0.94);
  background: rgba(255, 255, 255, 0.95);
}

.ort-call-page__frame--missing {
  background: #ebe4da;
}

.ort-call-page__img {
  display: block;
  width: 100%;
  max-height: 11rem;
  object-fit: contain;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.85);
}

.call-screen__main--ort .ort-call-page__img {
  width: 100%;
  height: 100%;
  max-height: 100%;
  border-radius: 0;
  background: transparent;
  object-fit: contain;
}

.ort-call-page__missing-label {
  position: absolute;
  left: 50%;
  bottom: 12%;
  transform: translateX(-50%);
  margin: 0;
  padding: 0.2rem 0.55rem;
  border-radius: 999px;
  font-size: 0.72rem;
  color: #8a7a68;
  background: rgba(255, 255, 255, 0.88);
}

.ort-call-page__meta {
  margin: 0.4rem 0 0;
  font-size: 0.78rem;
  opacity: 0.85;
}

.call-screen__main--ort .ort-call-page__meta {
  flex-shrink: 0;
  margin: 0;
  padding: 0.25rem 0.85rem 0;
}

.call-screen__main--ort .speed-field--call {
  padding: 0 0.85rem;
}

.call-screen__main--ort .script-panel--ort,
.call-screen__main--ort .turn-strip,
.call-screen__main--ort .call-screen__read-actions,
.call-screen__main--ort .call-screen__read-intro,
.call-screen__main--ort .call-screen__status {
  margin-left: 0.85rem;
  margin-right: 0.85rem;
  width: calc(100% - 1.7rem);
  max-width: none;
}

.script-panel--ort .script-panel__lines {
  max-height: 5rem;
}

.script-panel--ort {
  max-width: none;
}

.script-panel {
  width: 100%;
  max-width: 22rem;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 1rem;
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 22%, #fff);
  padding: 0.65rem 0.75rem 0.75rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.05);
}

.script-panel__label {
  font-size: 0.72rem;
  font-weight: 800;
  color: #94a3b8;
  margin-bottom: 0.45rem;
}

.script-panel__legend {
  font-weight: 700;
  color: #cbd5e1;
}

.script-panel__lines {
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  max-height: 32vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
}

.script-panel__line {
  font-size: 1.05rem;
  line-height: 1.45;
  padding: 0.45rem 0.55rem;
  border-radius: 0.65rem;
  color: #64748b;
  font-weight: 600;
}

.script-panel__line--active {
  background: color-mix(in srgb, var(--accent, #6366f1) 12%, #fff);
  color: #1e293b;
  font-weight: 800;
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 35%, #fff);
}

.script-panel__line--done {
  color: #94a3b8;
  text-decoration: line-through;
  text-decoration-color: rgba(148, 163, 184, 0.55);
}

.script-panel__line--pass {
  background: #ecfdf5;
  color: #047857;
  border: 2px solid #6ee7b7;
  font-weight: 700;
}

.script-panel__line--pass::after {
  content: " ✓";
  font-weight: 800;
}

.script-panel__line--almost {
  background: #fffbeb;
  color: #b45309;
  border: 2px solid #fcd34d;
  font-weight: 700;
}

.script-panel__line--almost::after {
  content: " ★";
}

.script-panel__line--retry {
  background: #fff7ed;
  color: #c2410c;
  border: 2px solid #fdba74;
  font-weight: 700;
}

.script-panel__line--retry::after {
  content: " ↻";
}

.script-panel__line--clickable {
  cursor: pointer;
}

.script-panel__line--clickable:active {
  transform: scale(0.99);
}

.speed-field {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.35rem;
}

.speed-field--call {
  flex-direction: row;
  align-items: center;
  justify-content: center;
  gap: 0.55rem;
  margin-top: 0;
  width: 100%;
  max-width: 22rem;
}

.speed-field__label {
  font-size: 0.78rem;
  font-weight: 800;
  color: #64748b;
}

.speed-field--call .speed-field__label {
  flex-shrink: 0;
  margin: 0;
}

.speed-segment {
  display: flex;
  width: 100%;
  padding: 0.28rem;
  border-radius: 0.85rem;
  background: #eef2ff;
  gap: 0.22rem;
}

.speed-segment--call {
  flex: 1;
  max-width: 15rem;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: inset 0 0 0 1px rgba(148, 163, 184, 0.22);
}

.speed-segment__btn {
  flex: 1;
  min-height: 2.55rem;
  padding: 0.5rem 0.65rem;
  border: none;
  border-radius: 0.62rem;
  background: transparent;
  font-size: 0.92rem;
  font-weight: 800;
  color: #64748b;
  transition:
    background 0.15s,
    color 0.15s,
    box-shadow 0.15s,
    transform 0.12s;
}

.speed-segment--call .speed-segment__btn {
  min-height: 2.35rem;
  font-size: 0.85rem;
}

.speed-segment__btn--active {
  background: #fff;
  color: var(--accent, #4f46e5);
  box-shadow: 0 2px 10px rgba(79, 70, 229, 0.14);
}

.speed-segment__btn:active:not(:disabled) {
  transform: scale(0.98);
}

.turn-strip {
  width: 100%;
  max-width: 22rem;
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.55rem 0.75rem;
  border-radius: 999px;
  font-weight: 800;
  font-size: 0.95rem;
}

.turn-strip--teacher {
  background: rgba(255, 255, 255, 0.9);
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 30%, #fff);
  color: var(--accent, #6366f1);
  flex-wrap: wrap;
  row-gap: 0.4rem;
}

.turn-strip__back {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  flex-shrink: 0;
  min-height: 2.35rem;
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 2px solid #fcd34d;
  background: #fffbeb;
  color: #b45309;
  font-size: 0.82rem;
  font-weight: 800;
  box-shadow: 0 4px 12px rgba(251, 191, 36, 0.18);
}

.turn-strip--child {
  background: #ecfdf5;
  border: 2px solid #34d399;
  color: #047857;
  animation: turn-pop 0.35s ease-out;
}

.turn-strip--busy {
  background: #f8fafc;
  border: 2px dashed #cbd5e1;
  color: #64748b;
}

.turn-strip--done {
  background: #fef9c3;
  border: 2px solid #fbbf24;
  color: #b45309;
}

.turn-strip__dot {
  width: 0.65rem;
  height: 0.65rem;
  border-radius: 50%;
  flex-shrink: 0;
  background: currentColor;
}

.turn-strip--busy .turn-strip__dot {
  border: 2px solid #94a3b8;
  border-top-color: transparent;
  background: transparent;
  animation: spin 0.8s linear infinite;
}

.turn-strip__text {
  flex: 1;
}

.turn-strip__waves {
  display: flex;
  gap: 0.2rem;
  align-items: flex-end;
  height: 1rem;
}

.turn-strip__waves span {
  width: 0.28rem;
  border-radius: 999px;
  background: #10b981;
  animation: wave-bar 0.75s ease-in-out infinite;
}

.turn-strip__waves span:nth-child(2) {
  animation-delay: 0.1s;
}
.turn-strip__waves span:nth-child(3) {
  animation-delay: 0.2s;
}

@keyframes turn-pop {
  0% {
    transform: scale(0.96);
    opacity: 0.7;
  }
  100% {
    transform: scale(1);
    opacity: 1;
  }
}

@keyframes wave-bar {
  0%,
  100% {
    height: 0.35rem;
  }
  50% {
    height: 1rem;
  }
}

.call-screen__status {
  font-size: 1.05rem;
  font-weight: 800;
  text-align: center;
  line-height: 1.35;
}

.btn--reread {
  width: 100%;
  min-height: 2.85rem;
  padding: 0.7rem 1rem;
  border-radius: 1rem;
  font-size: 1rem;
  font-weight: 800;
  color: var(--accent, #6366f1);
  background: rgba(255, 255, 255, 0.95);
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 35%, #fff);
  box-shadow: 0 6px 18px rgba(99, 102, 241, 0.12);
}

.btn--reread-back {
  color: #b45309;
  border-color: #fcd34d;
  background: #fffbeb;
  box-shadow: 0 6px 18px rgba(251, 191, 36, 0.15);
}

.btn--child-done {
  width: 100%;
  min-height: 3.35rem;
  padding: 0.85rem 1rem;
  border-radius: 1rem;
  font-size: 1.2rem;
  font-weight: 900;
  color: #fff;
  background: linear-gradient(145deg, #34d399, #059669);
  box-shadow: 0 10px 26px rgba(5, 150, 105, 0.35);
}

.btn--child-done:disabled {
  opacity: 0.55;
  box-shadow: none;
}

.call-screen__read-actions {
  display: flex;
  gap: 0.4rem;
  width: 100%;
  max-width: 22rem;
  margin-top: 0.15rem;
}

.btn-read-action {
  flex: 1;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 0.15rem;
  min-height: 2.35rem;
  padding: 0.4rem 0.3rem;
  border-radius: 0.65rem;
  border: 1.5px solid transparent;
  font-size: 0.68rem;
  font-weight: 800;
  line-height: 1.2;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 3px 10px rgba(15, 23, 42, 0.06);
}

.btn-read-action :deep(svg) {
  width: 0.95rem;
  height: 0.95rem;
}

.btn-read-action--prev {
  color: #b45309;
  border-color: #fcd34d;
  background: #fffbeb;
}

.btn-read-action--repeat {
  color: var(--accent, #6366f1);
  border-color: color-mix(in srgb, var(--accent, #6366f1) 35%, #fff);
}

.btn-read-action--done {
  color: #fff;
  background: linear-gradient(145deg, #34d399, #059669);
  border-color: #059669;
  box-shadow: 0 4px 12px rgba(5, 150, 105, 0.22);
}

.btn-read-action--next {
  color: #fff;
  background: linear-gradient(145deg, #5b7f5a, #3d5c3c);
  border-color: #3d5c3c;
  box-shadow: 0 4px 12px rgba(61, 92, 60, 0.22);
}

.btn-read-action--pause {
  color: #1d4ed8;
  border-color: #93c5fd;
  background: #eff6ff;
}

.btn-read-action--pause[aria-pressed="true"] {
  color: #fff;
  background: linear-gradient(145deg, #3b82f6, #1d4ed8);
  border-color: #1d4ed8;
  box-shadow: 0 4px 12px rgba(29, 78, 216, 0.22);
}

.btn-read-action:disabled {
  opacity: 0.38;
  box-shadow: none;
  pointer-events: none;
}

.call-screen__read-intro {
  font-size: 0.75rem;
  color: #64748b;
  text-align: center;
  line-height: 1.45;
  margin-bottom: 0.15rem;
}

.call-screen__parent-hint {
  font-size: 0.72rem;
  color: #64748b;
  text-align: center;
  line-height: 1.4;
  margin-top: -0.15rem;
}

.call-screen__interim {
  font-size: 0.9rem;
  padding: 0.45rem 0.9rem;
  background: rgba(255, 255, 255, 0.82);
  border-radius: 999px;
  max-width: 100%;
  text-align: center;
}

.call-screen__assistant {
  width: 100%;
  max-width: 22rem;
  padding: 0.75rem 0.95rem;
  background: rgba(255, 255, 255, 0.94);
  border-radius: 1.15rem;
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 30%, #fff);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
}

.call-screen__assistant-label {
  display: block;
  font-size: 0.72rem;
  font-weight: 800;
  color: var(--accent, #6366f1);
  margin-bottom: 0.25rem;
}

.call-screen__assistant-text {
  font-size: 1rem;
  line-height: 1.5;
  max-height: 28vh;
  overflow-y: auto;
  -webkit-overflow-scrolling: touch;
  word-break: break-word;
}

.call-screen__material {
  width: 100%;
  max-width: 22rem;
  font-size: 0.8rem;
  background: rgba(255, 255, 255, 0.82);
  border-radius: 0.85rem;
  padding: 0.25rem 0.5rem;
}

.call-screen__material summary {
  min-height: 2.75rem;
  display: flex;
  align-items: center;
  font-weight: 800;
  color: var(--accent, #6366f1);
  list-style: none;
  cursor: pointer;
}

.call-screen__material summary::-webkit-details-marker {
  display: none;
}

.call-screen__material pre {
  margin: 0 0 0.5rem;
  padding: 0 0.35rem 0.5rem;
  white-space: pre-wrap;
  word-break: break-word;
  line-height: 1.45;
  max-height: 22vh;
  overflow-y: auto;
}

.call-screen__mic-warn {
  width: 100%;
  max-width: 22rem;
  margin: 0.25rem 0 0;
  padding: 0.55rem 0.65rem;
  border-radius: 0.65rem;
  background: #fff7ed;
  border: 1px solid #fdba74;
  color: #9a3412;
  font-size: 0.78rem;
  font-weight: 600;
  line-height: 1.45;
  text-align: left;
}

.call-screen__error {
  color: #e11d48;
  font-weight: 600;
  text-align: center;
  padding: 0 0.5rem;
}

.call-screen__dock {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.5rem 0 max(env(safe-area-inset-bottom), 0.75rem);
  background: linear-gradient(
    180deg,
    transparent 0%,
    color-mix(in srgb, var(--hero-bg, #fff) 90%, #fff) 35%,
    color-mix(in srgb, var(--hero-bg, #fff) 98%, #fff) 100%
  );
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.btn--interrupt {
  width: 100%;
  min-height: 2.75rem;
  padding: 0.65rem 1rem;
  border-radius: 999px;
  border: 2px solid #fcd34d;
  background: #fffbeb;
  color: #b45309;
  font-weight: 800;
  font-size: 0.95rem;
}

.call-screen__textbar {
  display: flex;
  align-items: center;
  gap: 0.45rem;
}

.call-screen__input {
  flex: 1;
  min-width: 0;
  min-height: 2.75rem;
  padding: 0.6rem 0.95rem;
  border-radius: 999px;
  border: 2px solid color-mix(in srgb, var(--accent, #6366f1) 25%, #fff);
  background: #fff;
  font-size: 1rem;
}

.btn--send {
  flex-shrink: 0;
  min-height: 2.75rem;
  min-width: 3.25rem;
  padding: 0.6rem 1rem;
  border-radius: 999px;
  background: var(--btn-primary, linear-gradient(135deg, #6366f1, #8b5cf6));
  color: #fff;
  font-weight: 800;
  font-size: 0.95rem;
}

@media (max-width: 380px) {
  .call-screen__mode {
    font-size: 0.7rem;
  }

  .btn--send {
    min-width: 2.85rem;
    padding-inline: 0.75rem;
  }

  .call-screen__top--call {
    padding-right: 4.35rem;
    padding-left: 4.35rem;
  }

  .btn-hangup {
    padding: 0.35rem 0.6rem;
    font-size: 0.72rem;
  }
}

@media (min-height: 700px) {
  .call-screen__main:not(.call-screen__main--ort) {
    justify-content: center;
    padding-top: 0.5rem;
  }
}

/* PC：左图右操作，一屏无滚动 */
@media (min-width: 768px) {
  .app.app--ort-call {
    height: 100dvh;
    max-height: 100dvh;
    overflow: hidden;
  }

  .call-screen--ort {
    max-width: none;
    width: 100%;
    height: 100dvh;
    max-height: 100dvh;
    overflow: hidden;
    padding: 0;
    display: flex;
    flex-direction: column;
  }

  .call-screen--ort .call-screen__top--call {
    flex-shrink: 0;
    position: relative;
    padding-left: 1rem;
    padding-right: 1rem;
  }

  .call-screen--ort .call-screen__body {
    flex: 1;
    min-height: 0;
    overflow: hidden;
  }

  .call-screen--ort .call-screen__main--ort {
    display: grid;
    grid-template-columns: minmax(0, 1.28fr) minmax(17rem, 0.72fr);
    grid-template-rows: auto auto auto minmax(0, 1fr) auto auto;
    gap: 0.45rem 1rem;
    padding: 0.35rem 1rem 0.6rem;
    height: 100%;
    min-height: 0;
    overflow: hidden;
    align-content: stretch;
  }

  .call-screen--ort .ort-call-page {
    grid-column: 1;
    grid-row: 1 / -1;
    min-height: 0;
    margin: 0;
    display: flex;
    flex-direction: column;
    height: 100%;
  }

  .call-screen--ort .ort-call-page__frame {
    position: relative;
    flex: 1;
    min-height: 0;
    width: 100%;
    max-height: none;
    aspect-ratio: unset;
    margin: 0;
    background: #ebe6de;
    border-radius: 10px;
    overflow: hidden;
  }

  .call-screen--ort .ort-call-page__img {
    width: 100%;
    height: 100%;
    max-height: 100%;
    object-fit: contain;
  }

  .call-screen--ort .ort-call-page__nav {
    width: 3.1rem;
    height: 3.1rem;
    top: 50%;
  }

  .call-screen--ort .ort-call-page__meta {
    flex-shrink: 0;
    margin: 0;
    padding: 0.3rem 0 0;
    text-align: center;
    font-size: 0.78rem;
  }

  .call-screen--ort .speed-field--call {
    grid-column: 2;
    grid-row: 1;
    margin: 0;
    padding: 0;
    width: 100%;
    max-width: none;
    align-self: start;
  }

  .call-screen--ort .speed-segment--call {
    max-width: none;
  }

  .call-screen--ort .script-panel--ort {
    grid-column: 2;
    grid-row: 2;
    margin: 0;
    width: 100%;
    max-width: none;
    align-self: start;
  }

  .call-screen--ort .script-panel--ort .script-panel__lines {
    max-height: 8rem;
    overflow-y: auto;
  }

  .call-screen--ort .script-panel--ort .script-panel__line {
    font-size: 1.05rem;
    line-height: 1.35;
  }

  .call-screen--ort .turn-strip {
    grid-column: 2;
    grid-row: 3;
    margin: 0;
    width: 100%;
    max-width: none;
    align-self: start;
  }

  .call-screen--ort .call-screen__read-actions {
    grid-column: 2;
    grid-row: 5;
    margin: 0;
    width: 100%;
    max-width: none;
    align-self: end;
    gap: 0.45rem;
  }

  .call-screen--ort .call-screen__read-intro {
    grid-column: 2;
    grid-row: 6;
    margin: 0;
    width: 100%;
    max-width: none;
    font-size: 0.72rem;
    line-height: 1.35;
    text-align: left;
  }

  .call-screen--ort .call-screen__status {
    grid-column: 2;
    grid-row: 6;
    margin: 0;
    width: 100%;
    max-width: none;
  }

  .call-screen--ort .btn-read-action {
    min-height: 2.65rem;
    font-size: 0.72rem;
  }
}

@media (min-width: 1100px) {
  .call-screen--ort .call-screen__main--ort {
    grid-template-columns: minmax(0, 1.42fr) minmax(19rem, 0.58fr);
    gap: 0.55rem 1.25rem;
    padding-inline: 1.25rem;
  }

  .call-screen--ort .ort-call-page__nav {
    width: 3.5rem;
    height: 3.5rem;
  }

  .call-screen--ort .script-panel--ort .script-panel__line {
    font-size: 1.12rem;
  }

  .call-screen--ort .btn-read-action {
    min-height: 2.85rem;
    font-size: 0.78rem;
  }
}
</style>
