<script setup lang="ts">
import { revealSource } from "../source-navigation";
import { requestId as newRequestId } from "../request-id";
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useRoute } from "vue-router";
import { api, date, errorText, listHexagrams } from "../api";
import type { Reading, Attempt, ClassicSummary, Reflection } from "../types";
import Hexagram from "../components/Hexagram.vue";
import SourceCard from "../components/SourceCard.vue";
import CitedParagraph from "../components/CitedParagraph.vue";
const route = useRoute(),
  id = String(route.params.id || route.path.split("/").pop()),
  reading = ref<Reading>(),
  names = ref<ClassicSummary[]>([]),
  error = ref(""),
  attemptError = ref(""),
  busy = ref(false),
  selected = ref(""),
  reflection = ref(""),
  saving = ref(false),
  reflectionError = ref(""),
  useChoice = ref(""),
  useSaving = ref(false),
  useError = ref(""),
  now = ref(Date.now());
let disposed = false,
  timer: ReturnType<typeof setTimeout> | undefined;
const latest = computed(() => reading.value?.interpretations.at(-1)),
  successes = computed(
    () =>
      reading.value?.interpretations.filter(
        (a) => a.status === "succeeded" && a.result,
      ) || [],
  ),
  result = computed(
    () =>
      successes.value.find((a) => a.id === selected.value)?.result ||
      successes.value.at(-1)?.result,
  ),
  stale = computed(
    () =>
      latest.value?.status === "running" &&
      now.value - new Date(latest.value.started_at).getTime() > 600000,
  );
const sourceNumbers = computed(() => {
  const numbers: Record<string, number> = {};
  const value = result.value;
  if (!value) return numbers;
  const paragraphs = [
    value.summary,
    ...value.traditional,
    value.application,
    ...value.actions,
  ];
  for (const id of [
    ...value.citations.map((c) => c.source_id),
    ...paragraphs.flatMap((p) => p.source_ids),
  ]) {
    if (!(id in numbers)) numbers[id] = Object.keys(numbers).length + 1;
  }
  return numbers;
});
const primary = computed(
  () => reading.value?.materials.filter((m) => m.role === "primary") || [],
);
function name(id: number) {
  return names.value.find((n) => n.id === id)?.name || `第 ${id} 卦`;
}
function positionName(position: number) {
  return ["初爻", "二爻", "三爻", "四爻", "五爻", "上爻"][position - 1];
}
function safeUrl(value: string) {
  try {
    const url = new URL(value);
    return ["https:", "http:"].includes(url.protocol) ? url.href : undefined;
  } catch {
    return undefined;
  }
}
function schedule() {
  clearTimeout(timer);
  if (disposed || latest.value?.status !== "running") return;
  timer = setTimeout(async () => {
    now.value = Date.now();
    await load(false);
  }, 2000);
}
async function load(initial = true) {
  try {
    const value = await api<Reading>(`/readings/${encodeURIComponent(id)}`);
    if (disposed) return;
    reading.value = value;
    if (value.najia) {
      useChoice.value =
        value.najia.selected_use || value.najia.use_candidates[0] || "世爻";
    }
    error.value = "";
    if (initial && !value.interpretations.length && value.mode !== "najia") {
      await interpret(false);
    }
    schedule();
  } catch (e) {
    if (disposed) return;
    error.value = errorText(e);
    schedule();
  }
}
async function saveUseChoice() {
  if (!reading.value?.najia || useSaving.value || !useChoice.value) return false;
  useSaving.value = true;
  useError.value = "";
  try {
    reading.value = await api<Reading>(
      `/readings/${encodeURIComponent(id)}/najia-use`,
      { choice: useChoice.value },
    );
    return true;
  } catch (e) {
    useError.value = errorText(e);
    return false;
  } finally {
    useSaving.value = false;
  }
}
async function startNajiaInterpretation() {
  if (await saveUseChoice()) await interpret(false);
}
async function interpret(retry: boolean) {
  if (busy.value) return;
  busy.value = true;
  attemptError.value = "";
  const key = `zhouyi:attempt:${id}`;
  let requestId = sessionStorage.getItem(key);
  if (retry || !requestId) {
    requestId = newRequestId();
    sessionStorage.setItem(key, requestId);
  }
  try {
    const a = await api<Attempt>(
      `/readings/${encodeURIComponent(id)}/interpretations`,
      { request_id: requestId },
    );
    if (disposed) return;
    if (reading.value) {
      reading.value.interpretations = reading.value.interpretations
        .filter((x) => x.id !== a.id)
        .concat(a);
    }
    schedule();
  } catch (e) {
    attemptError.value = errorText(e);
  } finally {
    busy.value = false;
  }
}
async function saveReflection() {
  if (saving.value || !reflection.value.trim()) return;
  if (Array.from(reflection.value).length > 5000) {
    reflectionError.value = "笔记不能超过 5000 字";
    return;
  }
  const submittedText = reflection.value;
  saving.value = true;
  reflectionError.value = "";
  try {
    const value = await api<Reflection>(
      `/readings/${encodeURIComponent(id)}/reflections`,
      { text: submittedText.trim() },
    );
    reading.value?.reflections.push(value);
    if (reflection.value === submittedText) reflection.value = "";
  } catch (e) {
    reflectionError.value = errorText(e);
  } finally {
    saving.value = false;
  }
}
onMounted(() => {
  load();
  listHexagrams()
    .then((value) => {
      names.value = value;
    })
    .catch(() => {});
});
onUnmounted(() => {
  disposed = true;
  clearTimeout(timer);
});
</script>
<template>
  <el-alert
    v-if="error"
    :title="error"
    type="error"
    :closable="false"
  /><el-button v-if="error" @click="load()">重新加载</el-button
  ><template v-if="reading"
    ><section class="page-heading">
      <div>
        <p class="eyebrow">问卦记录 · {{ date(reading.created_at) }}</p>
        <h1>{{ reading.question.question }}</h1>
        <p class="muted" v-if="reading.question.horizon">
          关注时间：{{ reading.question.horizon }}
        </p>
        <p class="muted" v-if="reading.question.background">
          {{ reading.question.background }}
        </p>
      </div>
      <router-link to="/history">全部记录 →</router-link>
    </section>
    <div class="result-layout">
      <aside>
        <section class="panel cast-panel">
          <div class="hex-pair">
            <div>
              <p class="small-label">本卦</p>
              <Hexagram
                :bits="reading.cast.original_bits"
                :moving="reading.cast.moving"
              />
              <h2>{{ name(reading.cast.original_id) }}</h2>
            </div>
            <span class="change-arrow">→</span>
            <div>
              <p class="small-label">之卦</p>
              <Hexagram :bits="reading.cast.changed_bits" />
              <h2>{{ name(reading.cast.changed_id) }}</h2>
            </div>
          </div>
          <p class="muted">
            {{
              reading.cast.moving.length
                ? `变爻：${reading.cast.moving.join("、")}`
                : "六爻不变"
            }}
          </p>
          <details>
            <summary>查看六次随机结果</summary>
            <ol class="throws">
              <li v-for="(value, index) in reading.cast.values" :key="index">
                第 {{ index + 1 }} 次 ·
                {{ reading.cast.coins?.[index]?.join(" + ") || "已保存" }} =
                {{ value }}
                <span>{{
                  value === 6
                    ? "老阴"
                    : value === 7
                      ? "少阳"
                      : value === 8
                        ? "少阴"
                        : "老阳"
                }}</span>
              </li>
            </ol>
            <small>从初爻至上爻；此处展示已保存的随机结果。</small>
          </details>
        </section>
        <section class="reading-note compact">
          <p class="eyebrow">取辞依据</p>
          <p>{{ reading.selection.reason }}</p>
          <small>{{ reading.selection.version }}</small>
        </section>
      </aside>
      <div class="reading-main">
        <section v-if="reading.mode === 'najia' && reading.calendar && reading.najia" class="panel najia-panel">
          <div class="section-title">
            <div>
              <p class="eyebrow">{{ reading.najia.palace }}宫 · {{ reading.najia.palace_element }} · {{ reading.najia.palace_stage }}</p>
              <h2>六爻纳甲排盘</h2>
            </div>
            <span class="small-label">{{ reading.najia.version }}</span>
          </div>
          <p class="ganzhi-line">
            {{ reading.calendar.year_ganzhi }}年 · {{ reading.calendar.month_ganzhi }}月 ·
            {{ reading.calendar.day_ganzhi }}日 · {{ reading.calendar.hour_ganzhi }}时
          </p>
          <p class="muted">
            旬空：{{ reading.calendar.xunkong.join('、') }}；世爻在{{ positionName(reading.najia.shi_position) }}，
            应爻在{{ positionName(reading.najia.ying_position) }}。
          </p>
          <label class="use-picker">本次观察重点
            <select
              v-model="useChoice"
              data-testid="najia-use"
              :disabled="useSaving || reading.interpretations.length > 0"
              @change="saveUseChoice"
            >
              <option
                v-for="choice in ['世爻', '应爻', '父母', '兄弟', '子孙', '妻财', '官鬼']"
                :key="choice"
                :value="choice"
              >
                {{ choice }}{{ reading.najia.use_candidates.includes(choice) ? '（主题候选）' : '' }}
              </option>
            </select>
          </label>
          <p v-if="useError" class="error">{{ useError }}</p>
          <div class="najia-table">
            <div class="najia-row najia-head">
              <span>爻位</span><span>阴阳</span><span>纳甲</span><span>六亲</span><span>六神</span><span>世应</span><span>月日状态</span>
            </div>
            <div
              v-for="line in [...reading.najia.original_lines].reverse()"
              :key="line.position"
              class="najia-row"
              :class="{ moving: line.moving }"
              data-testid="najia-line"
            >
              <span>{{ positionName(line.position) }}</span>
              <span>{{ line.yin_yang }}{{ line.moving ? '动' : '' }}</span>
              <span>{{ line.stem_branch }}{{ line.element }}</span>
              <span>{{ line.relative }}</span>
              <span>{{ line.spirit }}</span>
              <span>{{ line.position === reading.najia.shi_position ? '世' : line.position === reading.najia.ying_position ? '应' : '' }}</span>
              <span>{{ [...line.flags, ...line.influences].join(' · ') || '—' }}</span>
            </div>
          </div>
          <p class="footnote">
            当前按北京时间零点换日，不使用真太阳时。排盘是固定规则计算，地点：{{ reading.question.location || '未填写' }}。
          </p>
          <details v-if="reading.najia.sources?.length">
            <summary>查看排盘规则依据</summary>
            <p v-for="source in reading.najia.sources" :key="source.source_url" class="muted">
              {{ source.book }} · {{ source.chapters.join('、') }} · {{ source.verification }}
              <a
                v-if="safeUrl(source.source_url)"
                :href="safeUrl(source.source_url)"
                data-testid="najia-source"
                target="_blank"
                rel="noopener noreferrer"
              >核对原文</a>
            </p>
          </details>
        </section>
        <section>
          <div class="section-title">
            <h2>先读原典</h2>
            <span class="small-label">本次主读</span>
          </div>
          <SourceCard
            v-for="material in primary"
            :anchor="false"
            :key="material.id"
            :material="material"
          />
          <p v-if="!primary.length" class="muted">暂无主读材料。</p>
        </section>
        <section class="panel interpretation">
          <div class="section-title">
            <h2>卦象启示与行动参考</h2>
            <el-select
              v-if="successes.length > 1"
              v-model="selected"
              placeholder="选择解读版本"
              style="width: 180px"
              ><el-option
                v-for="(a, index) in successes"
                :key="a.id"
                :value="a.id"
                :label="`解读 ${index + 1} · ${date(a.started_at)}`"
            /></el-select>
          </div>
          <div v-if="reading.mode === 'najia' && !reading.interpretations.length" class="status-box">
            <p>先确认上方的观察重点，再生成白话解读。</p>
            <el-button
              type="primary"
              data-testid="start-najia-interpretation"
              :loading="useSaving || busy"
              @click="startNajiaInterpretation"
            >按此重点生成解读</el-button>
          </div>
          <div
            v-if="latest?.status === 'running'"
            role="status"
            class="status-box"
          >
            <span class="status-dot" />正在解读，卦象已保存。
            <p class="muted">可以离开此页，稍后从记录中继续查看。</p>
          </div>
          <div v-if="latest?.status === 'failed'" class="error">
            <p>解读未完成：{{ latest.error || "服务暂时不可用" }}</p>
          </div>
          <p v-if="attemptError" class="error">{{ attemptError }}</p>
          <el-button
            v-if="latest?.status === 'failed' || stale || attemptError"
            data-testid="retry-interpretation"
            :loading="busy"
            @click="interpret(!!latest)"
            >{{ stale ? "解读等待较久，重新尝试" : "重试解读" }}</el-button
          ><template v-if="result"
            ><CitedParagraph
              :source-numbers="sourceNumbers"
              :paragraph="result.summary"
            />
            <h3>传统义理</h3>
            <CitedParagraph
              :source-numbers="sourceNumbers"
              v-for="(p, index) in result.traditional"
              :key="index"
              :paragraph="p"
            />
            <h3>回到此事</h3>
            <CitedParagraph
              :source-numbers="sourceNumbers"
              :paragraph="result.application"
            />
            <h3>可以做的事</h3>
            <ol>
              <li v-for="(p, index) in result.actions" :key="index">
                <CitedParagraph
                  :source-numbers="sourceNumbers"
                  :paragraph="p"
                />
              </li>
            </ol>
            <details v-if="result.citations.length">
              <summary>查看解读引文</summary>
              <blockquote
                v-for="(cite, index) in result.citations"
                :key="index"
              >
                <a
                  :href="`#source-${cite.source_id}`"
                  @click.prevent="revealSource(cite.source_id)"
                  >[{{ sourceNumbers[cite.source_id] }}]</a
                >
                {{ cite.quote }}
              </blockquote>
            </details>
            <p class="footnote">
              以上解读供自我反思参考；原典与解读分列，可自行核对。
            </p></template
          >
        </section>
        <details class="all-materials" open>
          <summary>本次全部出处 · {{ reading.materials.length }} 条</summary>
          <SourceCard
            v-for="material in reading.materials"
            :key="material.id"
            :material="material"
          />
        </details>
        <section class="panel">
          <h2>留下此刻的理解</h2>
          <p class="muted">之后回看，留意哪些判断与行动发生了变化。</p>
          <el-input
            v-model="reflection"
            aria-label="回看笔记"
            type="textarea"
            :rows="3"
            maxlength="5000"
            placeholder="我现在的理解，或后来发生的事…"
          />
          <p v-if="reflectionError" class="error">{{ reflectionError }}</p>
          <el-button
            class="reflection-button"
            :loading="saving"
            :disabled="!reflection.trim()"
            @click="saveReflection"
            >保存笔记</el-button
          >
          <article
            v-for="note in reading.reflections"
            :key="note.id"
            class="reflection"
          >
            <small>{{ date(note.created_at) }}</small>
            <p>{{ note.text }}</p>
          </article>
        </section>
      </div>
    </div></template
  ><el-skeleton v-else-if="!error" :rows="8" animated />
</template>
