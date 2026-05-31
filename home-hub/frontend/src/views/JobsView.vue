<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { fetchJobs } from '../api/dashboard'
import type { LaunchdJob } from '../types/dashboard'

const jobs = ref<LaunchdJob[]>([])
const error = ref('')

onMounted(async () => {
  try {
    const res = await fetchJobs()
    jobs.value = res.jobs
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
})
</script>

<template>
  <div class="page">
    <h1>定时任务（launchd）</h1>
    <p v-if="error" class="error">{{ error }}</p>

    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>状态</th>
            <th>Label</th>
            <th>调度</th>
            <th>入口</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="job in jobs" :key="job.label">
            <td>
              <span :class="job.loaded ? 'ok' : 'off'">{{ job.loaded ? '运行' : '未加载' }}</span>
            </td>
            <td class="mono">{{ job.label }}</td>
            <td>{{ job.schedule }}</td>
            <td class="entry">{{ job.entry }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0 0 16px;
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

.ok {
  color: #7dffb2;
}

.off {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}
</style>
