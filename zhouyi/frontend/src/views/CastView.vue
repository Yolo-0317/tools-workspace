<script setup lang="ts">
import { requestId as newRequestId } from "../request-id";
import { computed, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { api, errorText } from "../api";
import type { Topic, Question, Reading } from "../types";
import CyberCast from "../components/CyberCast.vue";
import { findRecentMatching } from "../question-history";
const router = useRouter(),
  topics = ref<Topic[]>([]),
  busy = ref(false),
  error = ref(""),
  topicsError = ref("");
const recentItems = ref<Pick<Reading, "id" | "question" | "created_at">[]>([]);
type CastForm = Question & {
  mode: "classic" | "najia";
  cast_time_local: string;
  location: string;
};
function beijingLocalNow() {
  const parts = new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());
  const value = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  return `${value.year}-${value.month}-${value.day}T${value.hour}:${value.minute}`;
}
function beijingIso(value: string) {
  return `${value}:00+08:00`;
}
const form = reactive<CastForm>({
  question: "",
  topic: "",
  background: "",
  horizon: "",
  mode: "classic",
  cast_time_local: beijingLocalNow(),
  location: "",
});
const animationReading = ref<Reading>();
const templates = computed(() =>
  form.topic ? topics.value.filter((t) => t.id === form.topic) : topics.value,
);
const recentMatch = computed(() => findRecentMatching(form.question, recentItems.value));
let fingerprint = "",
  requestId = "";
const pendingKey = "zhouyi:pending-cast";
try {
  const pending = JSON.parse(sessionStorage.getItem(pendingKey) || "null");
  if (
    pending &&
    typeof pending.requestId === "string" &&
    ["question", "topic", "background", "horizon"].every(
      (key) => typeof pending.form?.[key] === "string",
    )
  ) {
    Object.assign(form, pending.form);
    fingerprint = JSON.stringify(form);
    requestId = pending.requestId;
  }
} catch {
  sessionStorage.removeItem(pendingKey);
}
async function loadTopics() {
  try {
    topics.value = await api<Topic[]>("/topics");
    topicsError.value = "";
  } catch (e) {
    topicsError.value = errorText(e);
  }
}
async function loadRecent() {
  try {
    const value = await api<{ items: Pick<Reading, "id" | "question" | "created_at">[] }>("/readings?limit=100");
    if (Array.isArray(value.items)) recentItems.value = value.items;
  } catch {
    // This reminder is optional; casting remains available if history cannot load.
  }
}
onMounted(() => {
  loadTopics();
  loadRecent();
});
async function submit() {
  if (busy.value) return;
  if (!form.question.trim()) {
    error.value = "请先写下一个具体的问题。";
    return;
  }
  for (const [field, limit, label] of [
    ["question", 1000, "问题"],
    ["background", 3000, "背景"],
    ["horizon", 100, "关注时间"],
    ["location", 100, "所在地"],
  ] as const) {
    if (Array.from(form[field]).length > limit) {
      error.value = `${label}不能超过 ${limit} 字`;
      return;
    }
  }
  busy.value = true;
  error.value = "";
  const content = JSON.stringify(form);
  if (content !== fingerprint) {
    fingerprint = content;
    requestId = newRequestId();
  }
  try {
    sessionStorage.setItem(
      pendingKey,
      JSON.stringify({ form: { ...form }, requestId }),
    );
    const { cast_time_local, ...fields } = form;
    const reading = await api<Reading>("/readings", {
      ...fields,
      cast_time: form.mode === "najia" ? beijingIso(cast_time_local) : null,
      location: form.mode === "najia" ? form.location : "",
      request_id: requestId,
    });
    sessionStorage.removeItem(pendingKey);
    animationReading.value = reading;
  } catch (e) {
    error.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function finishAnimation() {
  const reading = animationReading.value;
  animationReading.value = undefined;
  if (reading) await router.push(`/readings/${reading.id}`);
}
</script>
<template>
  <CyberCast
    v-if="animationReading"
    :cast="animationReading.cast"
    @complete="finishAnimation"
    @skip="finishAnimation"
  />
  <section class="page-heading">
    <div>
      <p class="eyebrow">一事一问 · 六爻观变</p>
      <h1>把心中的事，问清楚。</h1>
      <p class="muted">从一个具体问题开始，读原典，也留意自己的处境。</p>
    </div>
    <span class="seal" aria-hidden="true">观易</span>
  </section>
  <div class="cast-layout">
    <section class="panel">
      <el-form label-position="top" @submit.prevent="submit"
        ><div class="mode-picker" aria-label="解读模式">
          <button
            type="button"
            :class="{ active: form.mode === 'classic' }"
            @click="form.mode = 'classic'"
          >经典取辞<small>依据经传和固定变占规则</small></button>
          <button
            type="button"
            data-testid="najia-mode"
            :class="{ active: form.mode === 'najia' }"
            @click="form.mode = 'najia'"
          >六爻纳甲<small>加入北京时间、世应和六亲</small></button>
        </div>
        <div v-if="form.mode === 'najia'" class="najia-inputs">
          <label>起卦时间（北京时间）
            <input v-model="form.cast_time_local" type="datetime-local" required />
          </label>
          <label>所在地（可选）
            <input v-model="form.location" data-testid="cast-location" maxlength="100" placeholder="例如：杭州" />
          </label>
          <small>第一版按北京时间零点换日，不使用真太阳时。</small>
        </div>
        <el-form-item label="此刻想问什么"
          ><el-input
            v-model="form.question"
            type="textarea"
            :rows="4"
            maxlength="1000"
            show-word-limit
            placeholder="例如：未来三个月，我应如何安排工作与学习？"
            :disabled="busy" /></el-form-item
        ><el-form-item label="选一个方向（可选）"
          ><el-radio-group v-model="form.topic" :disabled="busy"
            ><el-radio-button label="不限" value="" /><el-radio-button
              v-for="topic in topics"
              :key="topic.id"
              :label="topic.label"
              :value="topic.id" /></el-radio-group
        ></el-form-item>
        <p v-if="topicsError" class="error">
          {{ topicsError }}
          <button class="text-button" @click="loadTopics">重新加载题目</button>
        </p>
        <div class="templates">
          <span class="small-label">借一句话起笔，选后可修改</span
          ><template v-for="topic in templates" :key="topic.id"
            ><button
              v-for="template in topic.templates.slice(0, 2)"
              :key="template"
              type="button"
              data-testid="template"
              :disabled="busy"
              @click="
                form.question = template;
                form.topic = topic.id;
              "
            >
              {{ template }}
            </button></template
          >
        </div>
        <div class="form-pair">
          <el-form-item label="事情的背景（可选）"
            ><el-input
              v-model="form.background"
              :disabled="busy"
              maxlength="3000"
              placeholder="补充关键处境" /></el-form-item
          ><el-form-item label="关注的时间（可选）"
            ><el-input
              v-model="form.horizon"
              :disabled="busy"
              maxlength="100"
              placeholder="例如：未来三个月"
          /></el-form-item>
        </div>
        <div class="question-preview">
          <span class="small-label">本次所问</span>
          <p>{{ form.question.trim() || "写下问题后，在这里确认。" }}</p>
          <small v-if="form.horizon">时间：{{ form.horizon }}</small>
        </div>
        <el-alert
          v-if="recentMatch"
          type="warning"
          :closable="false"
          title="近 30 天问过相同的问题，建议先回看原卦和现实变化。"
        >
          <template #default>
            <router-link :to="`/readings/${recentMatch.id}`">查看原记录</router-link>，仍可继续本次起卦。
          </template>
        </el-alert>
        <el-alert
          v-if="error"
          :title="error"
          type="error"
          :closable="false"
          show-icon
        />
        <div class="submit-row">
          <el-button
            type="primary"
            size="large"
            :loading="busy"
            :disabled="!form.question.trim()"
            data-testid="cast"
            @click="submit"
            >{{
              busy ? "正在生成并保存六爻…" : "确认问题，开始起卦"
            }}</el-button
          ><small>一次起卦，自动完成六次信号汇聚</small>
        </div></el-form
      >
    </section>
    <aside class="reading-note">
      <p class="eyebrow">起卦之前</p>
      <h2>一卦聚焦一件事</h2>
      <p>让背景和你关心的问题尽量具体。</p>
      <div class="note-rule" />
      <h3>由下而上，观其变化</h3>
      <p>
        三组独立随机信号汇聚成一爻，初爻在下，上爻在上。卦象与问题一同保存，可随时回看。
      </p>
      <a href="/classics" @click.prevent="router.push('/classics')"
        >先读六十四卦 →</a
      >
      <p class="footnote">
        每次解读保留原文、出处和起卦过程，便于核对与回看。
      </p>
    </aside>
  </div>
</template>
