<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { api, errorText, listHexagrams } from "../api";
import type { Classic, ClassicSummary } from "../types";
import Hexagram from "../components/Hexagram.vue";
import SourceCard from "../components/SourceCard.vue";
const route = useRoute(),
  router = useRouter(),
  items = ref<ClassicSummary[]>([]),
  detail = ref<Classic>(),
  query = ref(""),
  error = ref(""),
  loading = ref(false);
const filtered = computed(() =>
  items.value.filter((x) => `${x.id} ${x.name}`.includes(query.value)),
);
const canonicalTexts = computed(() => {
  const value = detail.value;
  if (!value) return [];
  return [
    value.judgment,
    value.tuan,
    value.xiang,
    ...value.lines,
    ...value.xiaoxiang,
    ...(value.use ? [value.use] : []),
  ].filter(Boolean).map((material) => material.text);
});
let sequence = 0;
async function load() {
  const current = ++sequence;
  loading.value = true;
  try {
    if (!items.value.length) items.value = await listHexagrams();
    const id = Number(route.params.id) || items.value[0]?.id;
    if (!id) throw Error("暂时没有可读的原典。");
    const value = await api<Classic>(`/classics/${id}`);
    if (current !== sequence) return;
    detail.value = value;
    error.value = "";
  } catch (e) {
    if (current === sequence) error.value = errorText(e);
  } finally {
    if (current === sequence) loading.value = false;
  }
}
onMounted(load);
watch(() => route.params.id, load);
</script>
<template>
  <section class="page-heading">
    <div>
      <p class="eyebrow">原典 · 六十四卦</p>
      <h1>读一卦，留一点余地。</h1>
      <p class="muted">经文、传文与注疏分列，出处随文可查。</p>
    </div>
  </section>
  <div class="classics-layout">
    <aside class="classic-nav">
      <el-input
        v-model="query"
        aria-label="查找卦名或序号"
        clearable
        placeholder="查找卦名或序号"
      />
      <nav aria-label="六十四卦" class="classic-grid">
        <button
          v-for="item in filtered"
          :key="item.id"
          :class="{ active: detail?.id === item.id }"
          @click="router.push(`/classics/${item.id}`)"
        >
          <small>{{ String(item.id).padStart(2, "0") }}</small
          >{{ item.name }}
        </button>
      </nav>
    </aside>
    <section>
      <el-alert
        v-if="error"
        :title="error"
        type="error"
        :closable="false"
      /><el-button v-if="error" @click="load">重新加载</el-button
      ><el-skeleton v-if="loading" :rows="8" animated /><template
        v-else-if="detail"
        ><div class="classic-heading">
          <div>
            <p class="eyebrow">第 {{ detail.id }} 卦</p>
            <h2>{{ detail.name }}</h2>
          </div>
          <Hexagram :bits="detail.bits" />
        </div>
        <h3>卦辞</h3>
        <SourceCard :material="detail.judgment" />
        <h3>爻辞</h3>
        <SourceCard
          v-for="m in detail.lines"
          :key="m.id"
          :material="m"
        /><SourceCard v-if="detail.use" :material="detail.use" />
        <h3>彖传与象传</h3>
        <SourceCard v-if="detail.tuan" :material="detail.tuan" /><SourceCard
          v-if="detail.xiang"
          :material="detail.xiang"
        /><SourceCard v-for="m in detail.xiaoxiang" :key="m.id" :material="m" />
        <h3>注疏参读</h3>
        <p class="footnote">
          注疏为来源文本合并摘录，未经逐条人工编校。《周易正义》为部分收录，请结合版本与原始出处核对。
        </p>
        <SourceCard
          v-for="m in detail.commentaries"
          :key="m.id"
          :material="m"
          :canonical-texts="canonicalTexts"
        />
        <p v-if="!detail.commentaries.length" class="muted">
          此卦暂未收录注疏。
        </p></template
      >
    </section>
  </div>
</template>
