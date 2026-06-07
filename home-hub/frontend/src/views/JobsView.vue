<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { fetchJobs } from '../api/dashboard'
import { usePlatformLayout } from '../composables/usePlatformLayout'
import type { LaunchdJob } from '../types/dashboard'

const jobs = ref<LaunchdJob[]>([])
const error = ref('')
const loading = ref(true)
const isMobile = usePlatformLayout()

const loadedCount = computed(() => jobs.value.filter((j) => j.loaded).length)

function jobTitle(job: LaunchdJob): string {
  if (job.title?.trim()) return job.title.trim()
  return job.label.replace(/^com\.user\./, '').replace(/-/g, ' ')
}

function entryBase(entry: string): string {
  if (!entry) return '—'
  const parts = entry.split('/')
  return parts[parts.length - 1] || entry
}

function entryDir(entry: string): string {
  if (!entry) return ''
  const parts = entry.split('/')
  if (parts.length <= 1) return entry
  parts.pop()
  return parts.join('/')
}

onMounted(async () => {
  try {
    const res = await fetchJobs()
    jobs.value = res.jobs
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="page" :class="{ mobile: isMobile }">
    <header class="page-head">
      <h1>定时任务</h1>
      <p class="sub">launchd 本机任务 + Docker stock-ai-scheduler 定时（盘后链 17:30→17:45→18:00）</p>
    </header>

    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <template v-if="!loading && !error">
      <div v-if="jobs.length" class="summary">
        <span class="pill pill-ok">{{ loadedCount }} 运行中</span>
        <span class="pill pill-muted">共 {{ jobs.length }} 项</span>
      </div>

      <ul v-if="isMobile && jobs.length" class="job-list">
        <li
          v-for="job in jobs"
          :key="job.label"
          class="job-card"
          :class="job.loaded ? 'job-up' : 'job-off'"
        >
          <div class="job-head">
            <h3 class="job-name">{{ jobTitle(job) }}</h3>
            <span class="badge" :class="job.loaded ? 'ok' : 'off'">
              {{ job.loaded ? '运行' : '未加载' }}
            </span>
          </div>
          <p v-if="job.description" class="job-desc">{{ job.description }}</p>
          <p class="job-label mono">{{ job.label }}</p>
          <dl class="job-meta">
            <div class="meta-row">
              <dt>调度</dt>
              <dd>{{ job.schedule }}</dd>
            </div>
            <div class="meta-row">
              <dt>入口</dt>
              <dd>{{ entryBase(job.entry) }}</dd>
            </div>
          </dl>
          <p v-if="entryDir(job.entry)" class="entry-path mono">{{ entryDir(job.entry) }}</p>
        </li>
      </ul>

      <div v-else-if="jobs.length" class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>状态</th>
              <th>任务</th>
              <th>说明</th>
              <th>调度</th>
              <th>入口</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="job in jobs" :key="job.label">
              <td>
                <span class="badge inline" :class="job.loaded ? 'ok' : 'off'">
                  {{ job.loaded ? '运行' : '未加载' }}
                </span>
              </td>
              <td>
                <span class="job-table-title">{{ jobTitle(job) }}</span>
                <span class="job-table-label mono">{{ job.label }}</span>
              </td>
              <td class="job-table-desc">{{ job.description || '—' }}</td>
              <td>{{ job.schedule }}</td>
              <td class="entry">{{ job.entry }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <p v-else class="empty">暂无 launchd 任务配置</p>
    </template>
  </div>
</template>

<style scoped>
.page-head {
  margin-bottom: 14px;
}

.page-head h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin: 6px 0 0;
  font-size: 13px;
  color: #8b9cb3;
}

.summary {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
}

.pill {
  font-size: 12px;
  font-weight: 600;
  padding: 4px 12px;
  border-radius: 999px;
}

.pill-ok {
  color: #7dffb2;
  background: #10261c;
  border: 1px solid #1e3d2e;
}

.pill-muted {
  color: #8b9cb3;
  background: #121820;
  border: 1px solid #243041;
}

.job-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.job-card {
  padding: 14px;
  border-radius: 12px;
  border: 1px solid #243041;
  background: #121820;
}

.job-up {
  border-color: #1e3d2e;
  background: linear-gradient(135deg, #121820 0%, #0f1a14 100%);
}

.job-off {
  opacity: 0.92;
}

.job-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 6px;
}

.job-name {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  line-height: 1.3;
  color: #e7ecf3;
}

.job-desc {
  margin: 0 0 8px;
  font-size: 13px;
  line-height: 1.45;
  color: #a8b8d0;
}

.job-label {
  margin: 0 0 12px;
  font-size: 11px;
  color: #6b7d94;
  word-break: break-all;
}

.job-table-title {
  display: block;
  font-weight: 600;
  color: #e7ecf3;
  margin-bottom: 4px;
}

.job-table-label {
  display: block;
  font-size: 11px;
  color: #6b7d94;
}

.job-table-desc {
  font-size: 13px;
  color: #a8b8d0;
  line-height: 1.45;
  max-width: 280px;
}

.job-meta {
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.meta-row {
  display: grid;
  grid-template-columns: 44px 1fr;
  gap: 8px;
  align-items: start;
}

.meta-row dt {
  margin: 0;
  font-size: 12px;
  color: #6b7d94;
  line-height: 1.45;
}

.meta-row dd {
  margin: 0;
  font-size: 13px;
  color: #dbe7ff;
  line-height: 1.45;
  word-break: break-word;
}

.entry-path {
  margin: 10px 0 0;
  padding-top: 10px;
  border-top: 1px solid #243041;
  font-size: 11px;
  color: #6b7d94;
  word-break: break-all;
  line-height: 1.4;
}

.badge {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  padding: 3px 9px;
  border-radius: 999px;
  white-space: nowrap;
}

.badge.inline {
  display: inline-block;
}

.badge.ok {
  color: #7dffb2;
  background: #10261c;
}

.badge.off {
  color: #8b9cb3;
  background: #1a2030;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 12px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
}

th,
td {
  padding: 10px 12px;
  border-bottom: 1px solid #243041;
  text-align: left;
  vertical-align: top;
}

th {
  color: #8b9cb3;
  background: #0b1016;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 12px;
}

.entry {
  font-size: 12px;
  color: #8b9cb3;
  max-width: 420px;
  word-break: break-all;
}

.hint,
.empty {
  color: #8b9cb3;
  font-size: 14px;
}

.error {
  color: #ff8f8f;
  font-size: 14px;
}

.page.mobile .page-head h1 {
  font-size: 20px;
}

.page.mobile .job-name {
  font-size: 15px;
}
</style>
