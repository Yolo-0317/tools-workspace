<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { api, date, errorText } from "../api";
import type { Reading } from "../types";
import Hexagram from "../components/Hexagram.vue";
const items = ref<Pick<Reading, "id" | "question" | "cast" | "created_at" | "mode">[]>(
    [],
  ),
  total = ref(0),
  page = ref(1),
  loading = ref(true),
  error = ref("");
let sequence = 0;
let disposed = false;
async function load() {
  const current = ++sequence;
  loading.value = true;
  try {
    const value = await api<{ items: typeof items.value; total: number }>(
      `/readings?offset=${(page.value - 1) * 20}&limit=20`,
    );
    if (disposed || current !== sequence) return;
    items.value = value.items;
    total.value = value.total;
    error.value = "";
  } catch (e) {
    if (!disposed && current === sequence) error.value = errorText(e);
  } finally {
    if (!disposed && current === sequence) loading.value = false;
  }
}
onMounted(load);
onUnmounted(() => {
  disposed = true;
  sequence++;
});
function question(value: unknown) {
  return typeof value === "string"
    ? value
    : (value as { question?: string })?.question || "未命名问题";
}
</script>
<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">回看 · 观其往复</p>
      <h1>问过的事，都在这里。</h1>
      <p class="muted">重读当时的问题，也看看今日的自己。</p>
    </div>
    <router-link to="/">再问一事 →</router-link>
  </section>
  <el-alert
    v-if="error"
    :title="error"
    type="error"
    :closable="false"
  /><el-button v-if="error" @click="load">重新加载</el-button
  ><el-skeleton v-if="loading" :rows="5" animated />
  <div v-else-if="!items.length && !error" class="panel empty-state">
    <h2>还没有问卦记录</h2>
    <p class="muted">从一个具体的问题开始，给未来的自己留一份记录。</p>
    <router-link to="/">写下第一个问题 →</router-link>
  </div>
  <div v-else class="history-list">
    <router-link
      v-for="item in items"
      :key="item.id"
      :to="`/readings/${item.id}`"
      class="history-row"
      ><Hexagram :bits="item.cast.original_bits" :moving="item.cast.moving" />
      <div>
        <small>{{ date(item.created_at) }} · {{ item.mode === 'najia' ? '六爻纳甲' : '经典取辞' }}</small>
        <h2>{{ question(item.question) }}</h2>
        <p class="muted">
          {{
            item.cast.moving.length
              ? `${item.cast.moving.length} 爻变化`
              : "六爻不变"
          }}
          · 查看原典与解读
        </p>
      </div>
      <span class="row-arrow">→</span></router-link
    >
  </div>
  <el-pagination
    v-if="total > 20"
    v-model:current-page="page"
    :page-size="20"
    :total="total"
    layout="prev, pager, next"
    @current-change="load"
  />
</template>
