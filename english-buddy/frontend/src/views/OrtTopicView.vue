<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from "vue";
import type { Lesson } from "../api/client";
import { ORT_LEVEL_TABS, type OrtLevelFilter } from "../config/ort";
import type { OrtLessonGroup } from "../composables/useVoiceCallWs";
import {
  ortCoverUrl,
  ortFirstPageUrl,
  ortPlaceholderUrl,
  ortShortTitle,
} from "../utils/ortImageUrl";

const props = defineProps<{
  lessonGroups: OrtLessonGroup[];
  lessonsLoading: boolean;
  levelFilter: OrtLevelFilter;
  selectedLessonId: string | null;
  selectedLesson: Lesson | undefined;
  readAlongFull: boolean;
  readAlongLimitMessage: string;
  canStart: boolean;
  ttsSpeedPresets: ReadonlyArray<{ readonly id: string; readonly label: string }>;
  ttsSpeedPreset: string;
  programs: { id: string; title: string; page: { skin: string } }[];
  pickerProgramId: string;
  prewarmLabel: (lesson: Lesson) => string;
  lessonReady: (lesson: Lesson | undefined) => boolean;
  catalogError: string;
  listenOnlyHint: string;
  startButtonLabel: string;
  illustratedCount: number;
}>();

const emit = defineEmits<{
  setLevel: [level: OrtLevelFilter];
  selectLesson: [lessonId: string];
  selectProgram: [programId: string];
  setSpeed: [presetId: "slow" | "normal" | "fast"];
  startReadAlong: [lessonId: string];
}>();

const levelTabs = ORT_LEVEL_TABS;

const coverFallback = ref<Record<string, "page" | "placeholder">>({});
const sheetOpen = ref(false);

const flatLessons = computed(() =>
  props.lessonGroups.flatMap((group) =>
    group.lessons.map((lesson) => ({
      lesson,
      levelLabel: group.label,
    })),
  ),
);

function coverSrc(lessonId: string): string {
  const fb = coverFallback.value[lessonId];
  if (fb === "placeholder") return ortPlaceholderUrl();
  if (fb === "page") return ortFirstPageUrl(lessonId);
  return ortCoverUrl(lessonId);
}

function onCoverError(lessonId: string) {
  const fb = coverFallback.value[lessonId];
  if (!fb) {
    coverFallback.value = { ...coverFallback.value, [lessonId]: "page" };
    return;
  }
  if (fb === "page") {
    coverFallback.value = { ...coverFallback.value, [lessonId]: "placeholder" };
  }
}

function openLesson(lessonId: string) {
  emit("selectLesson", lessonId);
  sheetOpen.value = true;
}

function closeSheet() {
  sheetOpen.value = false;
}

function onPickChange(ev: Event) {
  const id = (ev.target as HTMLSelectElement).value;
  if (id) openLesson(id);
}

function onStartReadAlong() {
  if (!props.selectedLessonId || props.readAlongFull) return;
  emit("startReadAlong", props.selectedLessonId);
  closeSheet();
}

function onSheetKeydown(ev: KeyboardEvent) {
  if (ev.key === "Escape") closeSheet();
}

watch(
  () => props.levelFilter,
  () => {
    closeSheet();
  },
);

watch(sheetOpen, (open) => {
  if (typeof document === "undefined") return;
  document.body.style.overflow = open ? "hidden" : "";
});

onUnmounted(() => {
  if (typeof document !== "undefined") {
    document.body.style.overflow = "";
  }
});
</script>

<template>
  <section class="ort-topic">
    <header class="ort-topic__hero">
      <h1 class="ort-topic__title">牛津阅读树</h1>
      <p class="ort-topic__lead">
        {{ illustratedCount }} 本已配图 · 点封面开始 · 一句一页
      </p>
      <p v-if="illustratedCount === 0 && !lessonsLoading" class="ort-topic__lead-hint">
        暂无配图读本。未配图的课文请回<strong>首页</strong>选年级带读（纯文字）。
      </p>
    </header>

    <div class="ort-topic__toolbar">
      <div class="ort-level-tabs" role="tablist" aria-label="级别筛选">
        <button
          v-for="tab in levelTabs"
          :key="tab.id"
          type="button"
          role="tab"
          class="ort-level-tabs__btn"
          :class="{ 'ort-level-tabs__btn--active': levelFilter === tab.id }"
          :aria-selected="levelFilter === tab.id"
          @click="emit('setLevel', tab.id)"
        >
          {{ tab.label }}
        </button>
      </div>
    </div>

    <p v-if="lessonsLoading" class="ort-topic__status">加载课文…</p>
    <p v-else-if="catalogError" class="ort-topic__warn">{{ catalogError }}</p>
    <p v-else-if="readAlongFull" class="ort-topic__warn">
      {{ readAlongLimitMessage }}
    </p>

    <template v-else-if="lessonGroups.length">
      <div v-if="flatLessons.length" class="ort-topic__picker">
        <label class="ort-topic__picker-label" for="ort-lesson-select">快速选择</label>
        <select
          id="ort-lesson-select"
          class="ort-topic__select"
          :value="selectedLessonId ?? ''"
          @change="onPickChange"
        >
          <option value="" disabled>选一本读本…</option>
          <template v-for="group in lessonGroups" :key="group.level">
            <optgroup :label="group.label">
              <option
                v-for="lesson in group.lessons"
                :key="lesson.id"
                :value="lesson.id"
              >
                {{ ortShortTitle(lesson.title) }}
                {{ lessonReady(lesson) ? "" : "（预热中）" }}
              </option>
            </optgroup>
          </template>
        </select>
      </div>

      <div class="ort-book-sections">
        <section
          v-for="group in lessonGroups"
          :key="group.level"
          class="ort-book-section"
        >
          <h2 class="ort-book-section__title">{{ group.label }}</h2>
          <div class="ort-book-grid" role="list">
            <button
              v-for="lesson in group.lessons"
              :key="lesson.id"
              type="button"
              role="listitem"
              class="ort-book-card"
              :class="{
                'ort-book-card--active':
                  sheetOpen && selectedLessonId === lesson.id,
                'ort-book-card--ready': lessonReady(lesson),
              }"
              :aria-pressed="selectedLessonId === lesson.id"
              @click="openLesson(lesson.id)"
            >
              <div class="ort-book-card__cover">
                <img
                  class="ort-book-card__img"
                  :src="coverSrc(lesson.id)"
                  :alt="ortShortTitle(lesson.title)"
                  loading="lazy"
                  decoding="async"
                  @error="onCoverError(lesson.id)"
                />
                <span
                  class="ort-book-card__badge"
                  :class="{
                    'ort-book-card__badge--ready': lessonReady(lesson),
                  }"
                >
                  {{ lessonReady(lesson) ? "可带读" : "预热中" }}
                </span>
              </div>
              <p class="ort-book-card__title">{{ ortShortTitle(lesson.title) }}</p>
            </button>
          </div>
        </section>
      </div>
    </template>

    <p v-else class="ort-topic__empty">
      {{
        illustratedCount === 0
          ? "暂无配图读本，请回首页选课文带读"
          : "该级别暂无已配图读本"
      }}
    </p>

    <Teleport to="body">
      <div
        v-if="sheetOpen && selectedLesson"
        class="ort-sheet"
        role="dialog"
        aria-modal="true"
        :aria-label="`${ortShortTitle(selectedLesson.title)} 带读设置`"
        @keydown="onSheetKeydown"
      >
        <button
          type="button"
          class="ort-sheet__backdrop"
          aria-label="关闭"
          @click="closeSheet"
        />
        <div class="ort-sheet__panel">
          <button
            type="button"
            class="ort-sheet__close"
            aria-label="关闭"
            @click="closeSheet"
          >
            ×
          </button>

          <div class="ort-sheet__book">
            <img
              class="ort-sheet__cover"
              :src="coverSrc(selectedLesson.id)"
              :alt="ortShortTitle(selectedLesson.title)"
              decoding="async"
              @error="onCoverError(selectedLesson.id)"
            />
            <div class="ort-sheet__book-meta">
              <h2 class="ort-sheet__title">
                {{ ortShortTitle(selectedLesson.title) }}
              </h2>
              <p
                class="ort-sheet__status"
                :class="{
                  'ort-sheet__status--ready': lessonReady(selectedLesson),
                }"
              >
                {{ prewarmLabel(selectedLesson) }}
              </p>
            </div>
          </div>

          <p v-if="listenOnlyHint" class="ort-sheet__listen-hint">
            {{ listenOnlyHint }}
          </p>
          <p v-if="readAlongFull" class="ort-sheet__warn">
            {{ readAlongLimitMessage }}
          </p>

          <label class="ort-sheet__label">选老师</label>
          <div class="ort-sheet__teachers">
            <button
              v-for="p in programs"
              :key="p.id"
              type="button"
              class="ort-teacher-chip"
              :class="[
                `ort-teacher-chip--${p.page.skin}`,
                { 'ort-teacher-chip--active': pickerProgramId === p.id },
              ]"
              @click="emit('selectProgram', p.id)"
            >
              {{ p.title }}
            </button>
          </div>

          <label class="ort-sheet__label">语速</label>
          <div class="ort-sheet__speed" role="group" aria-label="语速">
            <button
              v-for="preset in ttsSpeedPresets"
              :key="preset.id"
              type="button"
              class="ort-speed-btn"
              :class="{ 'ort-speed-btn--active': ttsSpeedPreset === preset.id }"
              @click="emit('setSpeed', preset.id as 'slow' | 'normal' | 'fast')"
            >
              {{ preset.label }}
            </button>
          </div>

          <button
            type="button"
            class="ort-sheet__start"
            :disabled="!canStart || readAlongFull"
            @click="onStartReadAlong"
          >
            {{ startButtonLabel }}
          </button>
          <p
            v-if="!lessonReady(selectedLesson)"
            class="ort-sheet__hint"
          >
            课文预热中，请稍候再开始
          </p>
        </div>
      </div>
    </Teleport>
  </section>
</template>

<style scoped>
.ort-topic {
  padding: 0 1rem 1.25rem;
  max-width: 52rem;
  margin: 0 auto;
}

.ort-topic__hero {
  text-align: center;
  padding: 1.25rem 0 0.75rem;
}

.ort-topic__title {
  margin: 0;
  font-size: 1.5rem;
  font-weight: 700;
  color: #3d3428;
}

.ort-topic__lead {
  margin: 0.5rem 0 0;
  font-size: 0.9rem;
  color: #7a6e62;
  line-height: 1.5;
}

.ort-topic__lead-hint {
  margin: 0.65rem auto 0;
  max-width: 22rem;
  font-size: 0.78rem;
  line-height: 1.45;
  color: #8a6d3b;
  text-align: center;
}

.ort-topic__toolbar {
  margin: 1rem 0;
}

.ort-level-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  justify-content: center;
}

.ort-level-tabs__btn {
  padding: 0.35rem 0.75rem;
  border-radius: 999px;
  border: 1px solid #d4c4b0;
  background: #fff;
  font-size: 0.8rem;
  color: #5c5248;
  cursor: pointer;
}

.ort-level-tabs__btn--active {
  background: #5b7f5a;
  border-color: #5b7f5a;
  color: #fff;
}

.ort-topic__status,
.ort-topic__empty {
  text-align: center;
  color: #8a7a68;
  font-size: 0.9rem;
}

.ort-topic__warn {
  text-align: center;
  color: #b45309;
  font-size: 0.85rem;
  margin: 0.5rem 0;
}

.ort-topic__picker {
  margin-bottom: 1rem;
}

.ort-topic__picker-label {
  display: block;
  font-size: 0.78rem;
  font-weight: 700;
  color: #7a6e62;
  margin-bottom: 0.35rem;
}

.ort-topic__select {
  width: 100%;
  padding: 0.55rem 0.75rem;
  border-radius: 10px;
  border: 1px solid #d4c4b0;
  background: #fff;
  font-size: 0.9rem;
  color: #3d3428;
}

.ort-book-sections {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.ort-book-section__title {
  margin: 0 0 0.6rem;
  font-size: 0.95rem;
  font-weight: 700;
  color: #3d5c3c;
}

.ort-book-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 0.65rem;
}

.ort-book-card {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  padding: 0;
  border: 2px solid #e8dfd4;
  border-radius: 12px;
  background: #fff;
  overflow: hidden;
  cursor: pointer;
  text-align: left;
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease,
    transform 0.12s ease;
}

.ort-book-card:hover {
  border-color: #b8d4b6;
  box-shadow: 0 6px 18px rgba(61, 92, 60, 0.1);
}

.ort-book-card:active {
  transform: scale(0.98);
}

.ort-book-card--active {
  border-color: #5b7f5a;
  box-shadow: 0 0 0 2px rgba(91, 127, 90, 0.25);
}

.ort-book-card__cover {
  position: relative;
  aspect-ratio: 3 / 4;
  background: #f0ebe3;
  overflow: hidden;
}

.ort-book-card__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center top;
}

.ort-book-card__badge {
  position: absolute;
  top: 0.4rem;
  right: 0.4rem;
  padding: 0.15rem 0.45rem;
  border-radius: 999px;
  font-size: 0.62rem;
  font-weight: 800;
  color: #8a7a68;
  background: rgba(255, 255, 255, 0.92);
}

.ort-book-card__badge--ready {
  color: #3d5c3c;
  background: #e8f3e7;
}

.ort-book-card__title {
  margin: 0;
  padding: 0.45rem 0.5rem 0.55rem;
  font-size: 0.78rem;
  font-weight: 700;
  line-height: 1.3;
  color: #3d3428;
}

/* —— 选书弹层 —— */
.ort-sheet {
  position: fixed;
  inset: 0;
  z-index: 1200;
  display: flex;
  align-items: flex-end;
  justify-content: center;
  padding: 0;
}

.ort-sheet__backdrop {
  position: absolute;
  inset: 0;
  border: none;
  background: rgba(15, 23, 42, 0.45);
  cursor: pointer;
}

.ort-sheet__panel {
  position: relative;
  z-index: 1;
  width: 100%;
  max-width: 26rem;
  max-height: min(88dvh, 640px);
  overflow-y: auto;
  padding: 1rem 1.1rem calc(1.1rem + env(safe-area-inset-bottom));
  border-radius: 1.1rem 1.1rem 0 0;
  background: #fff;
  box-shadow: 0 -8px 32px rgba(15, 23, 42, 0.18);
}

.ort-sheet__close {
  position: absolute;
  top: 0.65rem;
  right: 0.65rem;
  width: 2rem;
  height: 2rem;
  border: none;
  border-radius: 999px;
  background: #f1f5f9;
  color: #64748b;
  font-size: 1.25rem;
  line-height: 1;
  cursor: pointer;
}

.ort-sheet__book {
  display: flex;
  gap: 0.85rem;
  align-items: center;
  margin-bottom: 0.85rem;
  padding-right: 1.75rem;
}

.ort-sheet__cover {
  flex-shrink: 0;
  width: 4.5rem;
  height: 6rem;
  object-fit: cover;
  object-position: center top;
  border-radius: 8px;
  background: #f0ebe3;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.ort-sheet__book-meta {
  min-width: 0;
}

.ort-sheet__title {
  margin: 0;
  font-size: 1.05rem;
  font-weight: 800;
  color: #3d3428;
  line-height: 1.3;
}

.ort-sheet__status {
  margin: 0.35rem 0 0;
  font-size: 0.78rem;
  color: #8a7a68;
}

.ort-sheet__status--ready {
  color: #3d5c3c;
}

.ort-sheet__listen-hint {
  margin: 0 0 0.75rem;
  font-size: 0.76rem;
  line-height: 1.45;
  color: #8a6d3b;
}

.ort-sheet__warn {
  margin: 0 0 0.75rem;
  font-size: 0.8rem;
  color: #b45309;
}

.ort-sheet__label {
  display: block;
  font-size: 0.78rem;
  font-weight: 700;
  color: #7a6e62;
  margin: 0.65rem 0 0.35rem;
}

.ort-sheet__label:first-of-type {
  margin-top: 0;
}

.ort-sheet__teachers {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
}

.ort-teacher-chip {
  padding: 0.45rem 0.8rem;
  border-radius: 999px;
  border: 1px solid #d4c4b0;
  background: #fff;
  font-size: 0.82rem;
  cursor: pointer;
}

.ort-teacher-chip--active {
  border-color: #5b7f5a;
  background: #eef5ed;
  color: #3d5c3c;
  font-weight: 600;
}

.ort-sheet__speed {
  display: flex;
  gap: 0.4rem;
}

.ort-speed-btn {
  flex: 1;
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid #d4c4b0;
  background: #fff;
  font-size: 0.82rem;
  cursor: pointer;
}

.ort-speed-btn--active {
  background: #5b7f5a;
  border-color: #5b7f5a;
  color: #fff;
}

.ort-sheet__start {
  display: block;
  width: 100%;
  margin-top: 1rem;
  padding: 0.9rem;
  border: none;
  border-radius: 12px;
  background: #5b7f5a;
  color: #fff;
  font-size: 1.05rem;
  font-weight: 700;
  cursor: pointer;
}

.ort-sheet__start:disabled {
  opacity: 0.45;
  cursor: default;
}

.ort-sheet__hint {
  margin: 0.5rem 0 0;
  text-align: center;
  font-size: 0.78rem;
  color: #8a7a68;
}

@media (min-width: 560px) {
  .ort-book-grid {
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.75rem;
  }
}

@media (min-width: 640px) {
  .ort-sheet {
    align-items: center;
    padding: 1.5rem;
  }

  .ort-sheet__panel {
    border-radius: 1.1rem;
    max-width: 22rem;
    max-height: min(90dvh, 520px);
    padding: 1.15rem 1.2rem 1.2rem;
  }
}

@media (min-width: 900px) {
  .ort-book-grid {
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.85rem;
  }

  .ort-book-card__title {
    font-size: 0.82rem;
  }
}
</style>
