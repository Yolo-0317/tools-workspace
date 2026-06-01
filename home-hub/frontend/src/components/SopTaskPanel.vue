<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { fetchSelectionSopJobs, type SelectionSopJob } from '../api/dashboard'

const emit = defineEmits<{
  update: [jobs: SelectionSopJob[]]
}>()

const jobs = ref<SelectionSopJob[]>([])
const activeCount = ref(0)
const loading = ref(true)
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)

const visible = computed(
  () => jobs.value.some((j) => j.status === 'queued' || j.status === 'running') || jobs.value.length > 0,
)

const statusLabel: Record<SelectionSopJob['status'], string> = {
  queued: '排队中',
  running: '执行中',
  done: '已完成',
  done_with_warning: '推送异常',
  failed: '失败',
}

function statusClass(status: SelectionSopJob['status']): string {
  if (status === 'queued') return 'st-queued'
  if (status === 'running') return 'st-running'
  if (status === 'done') return 'st-done'
  if (status === 'done_with_warning') return 'st-warn'
  return 'st-failed'
}

function formatTime(iso?: string): string {
  if (!iso) return '—'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return iso
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function jobTitle(job: SelectionSopJob): string {
  const name = (job.name || '').trim()
  return name ? `${name}（${job.code}）` : job.code
}

async function refresh() {
  try {
    const res = await fetchSelectionSopJobs(false, 20)
    jobs.value = res.jobs
    activeCount.value = res.active_count
    emit('update', res.jobs)
  } catch {
    /* 轮询失败静默，下次再试 */
  } finally {
    loading.value = false
  }
}

function startPoll() {
  stopPoll()
  pollTimer.value = setInterval(() => {
    void refresh()
  }, 3000)
}

function stopPoll() {
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
}

onMounted(async () => {
  await refresh()
  startPoll()
})

onUnmounted(stopPoll)

defineExpose({ refresh })
</script>

<template>
  <section v-if="visible" class="sop-tasks">
    <div class="sop-tasks-head">
      <h2 class="sop-tasks-title">东财 SOP 任务</h2>
      <span v-if="activeCount > 0" class="sop-tasks-badge">{{ activeCount }} 进行中</span>
      <span v-else-if="!loading" class="sop-tasks-badge muted">暂无进行中</span>
    </div>
    <p v-if="loading && !jobs.length" class="sop-tasks-hint">加载任务…</p>
    <ul v-else class="sop-task-list">
      <li
        v-for="job in jobs"
        :key="job.job_id"
        class="sop-task-item"
        :class="statusClass(job.status)"
      >
        <div class="sop-task-row">
          <span class="sop-task-name">{{ jobTitle(job) }}</span>
          <span class="sop-task-status" :class="statusClass(job.status)">
            <span
              v-if="job.status === 'queued' || job.status === 'running'"
              class="spinner"
              aria-hidden="true"
            />
            {{ statusLabel[job.status] }}
          </span>
        </div>
        <p class="sop-task-msg">{{ job.message || job.error || '—' }}</p>
        <p class="sop-task-meta">
          <span>选股日 {{ job.trade_date }}</span>
          <span>发起 {{ formatTime(job.created_at) }}</span>
          <span v-if="job.finished_at">完成 {{ formatTime(job.finished_at) }}</span>
        </p>
      </li>
    </ul>
    <p class="sop-tasks-foot">OpenCLI 串行执行，单股约 2～5 分钟；完成后推送到微信</p>
  </section>
</template>

<style scoped>
.sop-tasks {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  background: #121820;
  border: 1px solid #2a3548;
}

.sop-tasks-head {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 10px;
}

.sop-tasks-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  color: #e8eef7;
}

.sop-tasks-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
  background: #1e3a5f;
  color: #93c5fd;
}

.sop-tasks-badge.muted {
  background: #1a2230;
  color: #8b9cb3;
}

.sop-tasks-hint {
  margin: 0;
  font-size: 13px;
  color: #8b9cb3;
}

.sop-task-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.sop-task-item {
  padding: 10px 12px;
  border-radius: 8px;
  background: #0f141c;
  border: 1px solid #243044;
}

.sop-task-item.st-running,
.sop-task-item.st-queued {
  border-color: #3b4f6b;
  box-shadow: inset 3px 0 0 #3b82f6;
}

.sop-task-item.st-done {
  box-shadow: inset 3px 0 0 #22c55e;
}

.sop-task-item.st-warn {
  box-shadow: inset 3px 0 0 #f59e0b;
}

.sop-task-item.st-failed {
  box-shadow: inset 3px 0 0 #ef4444;
}

.sop-task-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.sop-task-name {
  font-size: 14px;
  font-weight: 600;
  color: #f3f6fb;
}

.sop-task-status {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  white-space: nowrap;
}

.st-queued,
.st-running {
  color: #93c5fd;
}

.st-done {
  color: #86efac;
}

.st-warn {
  color: #fcd34d;
}

.st-failed {
  color: #fca5a5;
}

.spinner {
  width: 12px;
  height: 12px;
  border: 2px solid #334155;
  border-top-color: #60a5fa;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.sop-task-msg {
  margin: 6px 0 0;
  font-size: 13px;
  color: #b8c5d9;
  line-height: 1.45;
}

.sop-task-meta {
  margin: 6px 0 0;
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  font-size: 11px;
  color: #6b7d94;
}

.sop-tasks-foot {
  margin: 10px 0 0;
  font-size: 11px;
  color: #6b7d94;
}
</style>
