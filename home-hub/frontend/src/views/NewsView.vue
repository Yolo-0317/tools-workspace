<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import {
  fetchNewsBriefings,
  fetchNewsItems,
  fetchNewsMeta,
} from '../api/dashboard'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import type { BriefingSnapshot, NewsItem, NewsMeta } from '../types/dashboard'

type CategoryFilter = 'all' | 'geo' | 'domestic'
type SentimentFilter = 'all' | 'bullish' | 'bearish' | 'neutral'

const meta = ref<NewsMeta | null>(null)
const items = ref<NewsItem[]>([])
const briefings = ref<BriefingSnapshot[]>([])
const selectedDate = ref(localToday())
const category = ref<CategoryFilter>('all')
const sentiment = ref<SentimentFilter>('all')
const selectedSlot = ref('')
const error = ref('')
const loading = ref(true)
const listLoading = ref(false)
const isMobile = usePlatformLayout()

function localToday(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const categoryLabel: Record<string, string> = {
  geo: '地缘',
  domestic: '国内',
  other: '其他',
}

const sentimentLabel: Record<string, string> = {
  bullish: '利好',
  bearish: '利空',
  neutral: '中性',
}

function itemSentiment(item: NewsItem): string {
  return sentimentLabel[item.sentiment] || sentimentLabel.neutral
}

const filteredItems = computed(() => items.value)

const listHint = computed(() => {
  const n = filteredItems.value.length
  if (sentiment.value === 'all' && category.value === 'all') {
    return `共 ${n} 条`
  }
  const parts: string[] = []
  if (category.value !== 'all') parts.push(categoryLabel[category.value] || category.value)
  if (sentiment.value !== 'all') parts.push(sentimentLabel[sentiment.value] || sentiment.value)
  return `${parts.join(' · ')} ${n} 条`
})

function setSentiment(next: SentimentFilter) {
  sentiment.value = next
}

const activeBriefing = computed(() => {
  if (!briefings.value.length) return null
  if (selectedSlot.value) {
    return briefings.value.find((b) => b.slot === selectedSlot.value) ?? briefings.value[0]
  }
  return briefings.value[0]
})

const refreshing = ref(false)

async function refresh() {
  refreshing.value = true
  error.value = ''
  try {
    await loadAll()
  } finally {
    refreshing.value = false
  }
}

const lastFetchText = computed(() => {
  const lf = meta.value?.last_fetch
  if (!lf?.finished_at) return '—'
  const ok = lf.ok ? '' : '（失败）'
  const t = lf.finished_at
  const short = t.length >= 16 ? t.slice(11, 16) : t
  return `${short}${ok}`
})

function itemTime(item: NewsItem): string {
  if (item.news_time) return item.news_time
  if (item.published_at) return item.published_at.slice(11, 16)
  return '—'
}

function summaryText(item: NewsItem): string {
  const s = item.summary?.trim()
  if (!s || s === item.title) return ''
  return s.length > 140 ? `${s.slice(0, 140)}…` : s
}

async function loadItems() {
  listLoading.value = true
  error.value = ''
  try {
    const cat = category.value === 'all' ? undefined : category.value
    const sent = sentiment.value === 'all' ? undefined : sentiment.value
    const list = await fetchNewsItems({
      date: selectedDate.value,
      category: cat,
      sentiment: sent,
      limit: sent || cat ? 100 : 80,
    })
    items.value = list.items
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    listLoading.value = false
  }
}

async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [m, , b] = await Promise.all([
      fetchNewsMeta(selectedDate.value),
      loadItems(),
      fetchNewsBriefings(selectedDate.value),
    ])
    meta.value = m
    briefings.value = b.briefings
    if (b.briefings.length && !selectedSlot.value) {
      selectedSlot.value = b.briefings[0].slot
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

watch(selectedDate, () => {
  selectedSlot.value = ''
  loadAll()
})

watch([category, sentiment], () => {
  void loadItems()
})

onMounted(loadAll)
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="page-head">
      <div class="head-row">
        <div>
          <h1>财经快讯</h1>
          <p class="sub">东财 7×24 · Cursor AI 解读（每 15 分钟更新）</p>
        </div>
        <button
          type="button"
          class="refresh-btn"
          :disabled="loading || refreshing"
          @click="refresh"
        >
          {{ refreshing ? '刷新中…' : '刷新' }}
        </button>
      </div>
    </header>

    <label class="date-field">
      <span class="date-label">查看日期</span>
      <input v-model="selectedDate" type="date" class="date-select" :disabled="loading" />
    </label>

    <p v-if="error" class="error">{{ error }}</p>
    <p v-if="loading" class="hint">加载中…</p>

    <template v-if="!loading && meta">
      <div class="summary">
        <span class="pill pill-muted">今日 {{ meta.total_today ?? 0 }} 条</span>
        <span class="pill pill-muted">地缘 {{ meta.counts?.geo ?? 0 }}</span>
        <span class="pill pill-muted">国内 {{ meta.counts?.domestic ?? 0 }}</span>
        <button
          type="button"
          class="pill pill-bullish pill-btn"
          :class="{ active: sentiment === 'bullish' }"
          @click="setSentiment(sentiment === 'bullish' ? 'all' : 'bullish')"
        >
          利好 {{ meta.sentiment_counts?.bullish ?? 0 }}
        </button>
        <button
          type="button"
          class="pill pill-bearish pill-btn"
          :class="{ active: sentiment === 'bearish' }"
          @click="setSentiment(sentiment === 'bearish' ? 'all' : 'bearish')"
        >
          利空 {{ meta.sentiment_counts?.bearish ?? 0 }}
        </button>
        <span class="pill pill-muted">中性 {{ meta.sentiment_counts?.neutral ?? 0 }}</span>
        <span class="pill pill-muted">同步 {{ lastFetchText }}</span>
      </div>

      <section v-if="briefings.length" class="section">
        <h2 class="section-title">AI 解读（Cursor）</h2>
        <div class="slot-tabs">
          <button
            v-for="b in briefings"
            :key="b.slot"
            type="button"
            class="slot-tab"
            :class="{ active: selectedSlot === b.slot }"
            @click="selectedSlot = b.slot"
          >
            {{ b.slot }}
          </button>
        </div>
        <article v-if="activeBriefing" class="briefing-card">
          <p class="briefing-head">
            {{ activeBriefing.title || activeBriefing.slot }}
            <span v-if="activeBriefing.created_at" class="muted briefing-time">
              · {{ activeBriefing.created_at.slice(11, 16) }}
            </span>
          </p>
          <div v-if="activeBriefing.ai_summary" class="briefing-body">{{
            activeBriefing.ai_summary
          }}</div>
          <p v-else class="empty-text">该时段暂无 AI 解读</p>
        </article>
      </section>

      <section class="section">
        <div class="filter-row">
          <h2 class="section-title inline">快讯列表</h2>
          <span v-if="!loading" class="list-count">{{ listHint }}</span>
        </div>
        <div class="filter-row filters-stack">
          <div class="cat-tabs" role="tablist" aria-label="分类筛选">
            <button
              type="button"
              class="cat-tab"
              :class="{ active: category === 'all' }"
              @click="category = 'all'"
            >
              全部
            </button>
            <button
              type="button"
              class="cat-tab"
              :class="{ active: category === 'geo' }"
              @click="category = 'geo'"
            >
              地缘
            </button>
            <button
              type="button"
              class="cat-tab"
              :class="{ active: category === 'domestic' }"
              @click="category = 'domestic'"
            >
              国内
            </button>
          </div>
          <div class="cat-tabs sentiment-tabs" role="tablist" aria-label="情绪筛选">
            <button
              type="button"
              class="cat-tab"
              :class="{ active: sentiment === 'all' }"
              @click="setSentiment('all')"
            >
              全部
            </button>
            <button
              type="button"
              class="cat-tab sentiment-bullish"
              :class="{ active: sentiment === 'bullish' }"
              @click="setSentiment('bullish')"
            >
              利好
            </button>
            <button
              type="button"
              class="cat-tab sentiment-bearish"
              :class="{ active: sentiment === 'bearish' }"
              @click="setSentiment('bearish')"
            >
              利空
            </button>
            <button
              type="button"
              class="cat-tab"
              :class="{ active: sentiment === 'neutral' }"
              @click="setSentiment('neutral')"
            >
              中性
            </button>
          </div>
        </div>

        <p v-if="listLoading" class="hint list-loading">筛选中…</p>

        <ul v-if="filteredItems.length && !listLoading" class="news-list">
          <li v-for="item in filteredItems" :key="item.id" class="news-card">
            <div class="news-head">
              <span class="news-time">{{ itemTime(item) }}</span>
              <span
                class="sentiment-badge"
                :class="{
                  bullish: item.sentiment === 'bullish',
                  bearish: item.sentiment === 'bearish',
                  neutral: !item.sentiment || item.sentiment === 'neutral',
                }"
              >
                {{ itemSentiment(item) }}
              </span>
              <span class="cat-badge">{{ categoryLabel[item.category] || item.category }}</span>
            </div>
            <a :href="item.href" target="_blank" rel="noopener noreferrer" class="news-title">
              {{ item.title }}
            </a>
            <p v-if="summaryText(item)" class="news-summary">{{ summaryText(item) }}</p>
          </li>
        </ul>
        <div v-else-if="!listLoading" class="section-empty">
          <p class="empty-text">
            {{
              sentiment !== 'all' || category !== 'all'
                ? '当前筛选条件下暂无快讯'
                : '该日暂无快讯（等待同步或切换日期）'
            }}
          </p>
        </div>
      </section>
    </template>
  </div>
</template>

<style scoped>
.page {
  width: 100%;
  max-width: 100%;
  min-width: 0;
  overflow-x: hidden;
  touch-action: pan-y;
}

.page-head {
  margin-bottom: 14px;
}

.head-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  min-width: 0;
}

.head-row > div:first-child {
  flex: 1;
  min-width: 0;
}

.refresh-btn {
  flex-shrink: 0;
  font-size: 13px;
  font-weight: 600;
  padding: 8px 14px;
  border-radius: 10px;
  border: 1px solid #3d5a80;
  background: #1a2433;
  color: #e7ecf3;
  cursor: pointer;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-head h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8b9cb3;
  line-height: 1.45;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.date-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 14px;
}

.date-label {
  font-size: 12px;
  font-weight: 600;
  color: #6b7d94;
}

.date-select {
  width: 100%;
  max-width: 100%;
  background: #121820;
  color: #e7ecf3;
  border: 1px solid #243041;
  border-radius: 10px;
  padding: 12px 14px;
  font-size: 15px;
  box-sizing: border-box;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
  max-width: 100%;
}

.pill {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
  max-width: 100%;
  white-space: normal;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.pill-muted {
  color: #8b9cb3;
  background: #121820;
  border: 1px solid #243041;
}

.section {
  margin-bottom: 18px;
  min-width: 0;
  max-width: 100%;
}

.section-title {
  margin: 0 0 10px;
  font-size: 13px;
  font-weight: 600;
  color: #8b9cb3;
}

.section-title.inline {
  margin: 0;
}

.filter-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
  min-width: 0;
}

.cat-tabs,
.slot-tabs {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-width: 100%;
  min-width: 0;
}

.cat-tab,
.slot-tab {
  font-size: 12px;
  padding: 6px 12px;
  border-radius: 999px;
  border: 1px solid #243041;
  background: #121820;
  color: #8b9cb3;
  cursor: pointer;
}

.cat-tab.active,
.slot-tab.active {
  color: #e7ecf3;
  border-color: #3d5a80;
  background: #1a2433;
}

.briefing-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.briefing-head {
  margin: 0 0 10px;
  font-size: 13px;
  color: #8b9cb3;
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.briefing-body {
  margin: 0;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
  word-break: break-word;
  font-family: inherit;
  font-size: 14px;
  line-height: 1.55;
  color: #e7ecf3;
  max-width: 100%;
}

.news-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-width: 0;
  max-width: 100%;
}

.news-card {
  padding: 12px 14px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
  min-width: 0;
  max-width: 100%;
  overflow: hidden;
}

.news-head {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 6px;
}

.news-time {
  font-size: 12px;
  color: #6b7d94;
  font-variant-numeric: tabular-nums;
}

.sentiment-badge {
  font-size: 11px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: 999px;
}

.sentiment-badge.bullish {
  color: #7ee0a8;
  background: rgba(46, 125, 80, 0.25);
  border: 1px solid rgba(126, 224, 168, 0.35);
}

.sentiment-badge.bearish {
  color: #ffb4b4;
  background: rgba(160, 48, 48, 0.25);
  border: 1px solid rgba(255, 180, 180, 0.35);
}

.sentiment-badge.neutral {
  color: #8b9cb3;
  background: #1a2433;
  border: 1px solid #243041;
}

.pill-bullish {
  color: #7ee0a8;
  background: rgba(46, 125, 80, 0.2);
  border: 1px solid rgba(126, 224, 168, 0.3);
}

.pill-bearish {
  color: #ffb4b4;
  background: rgba(160, 48, 48, 0.2);
  border: 1px solid rgba(255, 180, 180, 0.3);
}

.pill-btn {
  cursor: pointer;
  font: inherit;
}

.pill-btn.active {
  box-shadow: 0 0 0 2px rgba(126, 224, 168, 0.35);
}

.pill-bearish.pill-btn.active {
  box-shadow: 0 0 0 2px rgba(255, 180, 180, 0.35);
}

.list-count {
  font-size: 12px;
  color: #6b7d94;
  white-space: nowrap;
}

.filters-stack {
  flex-direction: column;
  align-items: stretch;
}

.sentiment-tabs .cat-tab.sentiment-bullish.active {
  color: #7ee0a8;
  border-color: rgba(126, 224, 168, 0.45);
  background: rgba(46, 125, 80, 0.2);
}

.sentiment-tabs .cat-tab.sentiment-bearish.active {
  color: #ffb4b4;
  border-color: rgba(255, 180, 180, 0.45);
  background: rgba(160, 48, 48, 0.2);
}

.list-loading {
  margin: 0 0 10px;
}

.cat-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #1a2433;
  color: #8b9cb3;
}

.news-title {
  display: block;
  font-size: 15px;
  font-weight: 600;
  color: #e7ecf3;
  text-decoration: none;
  line-height: 1.4;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.news-title:hover {
  color: #9ec5ff;
}

.news-summary {
  margin: 8px 0 0;
  font-size: 13px;
  line-height: 1.45;
  color: #8b9cb3;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.section-empty {
  padding: 20px 14px;
  border-radius: 12px;
  border: 1px dashed #243041;
  background: #121820;
  text-align: center;
}

.empty-text {
  margin: 0;
  font-size: 14px;
  color: #6b7d94;
}

.muted {
  color: #6b7d94;
}

.error {
  color: #ffb4b4;
  margin-bottom: 10px;
}

.hint {
  color: #8b9cb3;
}

.page.mobile .page-head h1 {
  font-size: 20px;
  overflow-wrap: anywhere;
  word-break: break-word;
}

.page.mobile .head-row {
  flex-direction: column;
  align-items: stretch;
}

.page.mobile .refresh-btn {
  width: 100%;
  margin-top: 4px;
}

.page.mobile .sub {
  font-size: 12px;
}

.page.mobile .date-field {
  width: 100%;
  max-width: 100%;
}

.page.mobile .date-select {
  min-height: 48px;
  width: 100%;
  min-width: 0;
  max-width: 100%;
  -webkit-appearance: none;
  appearance: none;
}

.page.mobile .summary {
  gap: 6px;
}

.page.mobile .pill {
  font-size: 11px;
  padding: 4px 10px;
}

.page.mobile .filter-row {
  flex-direction: column;
  align-items: stretch;
}

.page.mobile .cat-tabs {
  width: 100%;
}

.page.mobile .slot-tabs {
  width: 100%;
}

.page.mobile .briefing-body {
  font-size: 13px;
  overflow-x: hidden;
}
</style>
