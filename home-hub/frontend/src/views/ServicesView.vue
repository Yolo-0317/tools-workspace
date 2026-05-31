<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  fetchJellyfinMappings,
  fetchServicesCatalog,
  healthClass,
  healthLabel,
} from '../api/services'
import type { JellyfinMappings, ServiceCategory } from '../types/services'

const categories = ref<ServiceCategory[]>([])
const domains = ref<Record<string, unknown>>({})
const dockerRunning = ref<string[]>([])
const jellyfin = ref<JellyfinMappings | null>(null)
const error = ref('')
const loading = ref(true)
const showJellyfin = ref(false)

async function load() {
  loading.value = true
  error.value = ''
  try {
    const [catalog, jf] = await Promise.all([
      fetchServicesCatalog(),
      fetchJellyfinMappings(),
    ])
    categories.value = catalog.categories
    domains.value = catalog.domains
    dockerRunning.value = catalog.docker_containers_running
    jellyfin.value = jf
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  } finally {
    loading.value = false
  }
}

function copyText(text: string) {
  navigator.clipboard?.writeText(text)
}

onMounted(load)
</script>

<template>
  <div class="page">
    <h1>本地服务</h1>
    <p v-if="loading" class="hint">加载中…</p>
    <p v-if="error" class="error">{{ error }}</p>

    <p v-if="domains.public_https_hint" class="meta">
      公网 HTTPS：{{ domains.public_https_hint }}
      <span v-if="domains.external_https_port">（外网端口 {{ domains.external_https_port }}）</span>
    </p>

    <section v-for="cat in categories" :key="cat.id" class="block">
      <h2>{{ cat.name }}</h2>
      <div class="cards">
        <article v-for="item in cat.items" :key="item.id" class="card">
          <div class="card-head">
            <h3>{{ item.name }}</h3>
            <span class="badge" :class="healthClass(item.health?.status)">
              {{ healthLabel(item.health?.status) }}
            </span>
          </div>
          <p v-if="item.description" class="desc">{{ item.description }}</p>

          <ul class="links">
            <li v-if="item.local_url">
              本机
              <a :href="item.local_url" target="_blank" rel="noopener">{{ item.local_url }}</a>
              <button type="button" class="copy" @click="copyText(item.local_url!)">复制</button>
            </li>
            <li v-if="item.dev_url">
              开发
              <a :href="item.dev_url" target="_blank" rel="noopener">{{ item.dev_url }}</a>
              <button type="button" class="copy" @click="copyText(item.dev_url!)">复制</button>
            </li>
            <li v-if="item.public_url">
              公网
              <a :href="item.public_url" target="_blank" rel="noopener">{{ item.public_url }}</a>
              <button type="button" class="copy" @click="copyText(item.public_url!)">复制</button>
            </li>
            <li v-if="item.public_note">{{ item.public_note }}</li>
            <li v-if="item.health_note" class="hint">{{ item.health_note }}</li>
            <li v-if="item.compose_dir">Compose：{{ item.compose_dir }}</li>
            <li v-if="item.docker_container">
              容器 {{ item.docker_container }}
              <span :class="item.docker_running ? 'ok-text' : 'down-text'">
                {{ item.docker_running ? '运行中' : '未运行' }}
              </span>
            </li>
          </ul>

          <div v-if="Object.keys(item.credentials).length" class="creds">
            <strong>凭据 env</strong>
            <ul>
              <li v-for="(st, key) in item.credentials" :key="key">
                <code>{{ key }}</code> — {{ st }}
              </li>
            </ul>
          </div>
        </article>
      </div>
    </section>

    <section class="block">
      <div class="block-head">
        <h2>Jellyfin 媒体映射</h2>
        <button type="button" class="toggle" @click="showJellyfin = !showJellyfin">
          {{ showJellyfin ? '收起' : '展开' }}（{{ jellyfin?.total_items ?? 0 }} 条）
        </button>
      </div>
      <p v-if="jellyfin" class="meta">Stack：{{ jellyfin.stack_dir }}</p>
      <template v-if="showJellyfin && jellyfin">
        <div v-for="lib in jellyfin.libraries" :key="lib.list_file" class="jf-lib">
          <h3>{{ lib.library }} · {{ lib.staging_prefix }}（{{ lib.count }}）</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>标题</th>
                  <th>季</th>
                  <th>Staging</th>
                  <th>源路径</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(row, i) in lib.items" :key="i">
                  <td>{{ row.title }}</td>
                  <td>{{ row.season || '—' }}</td>
                  <td class="mono">{{ row.staging }}</td>
                  <td class="mono">{{ row.source }}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </template>
    </section>

    <section class="block">
      <h2>Docker 运行中（{{ dockerRunning.length }}）</h2>
      <p class="mono wrap">{{ dockerRunning.join(', ') || '—' }}</p>
    </section>
  </div>
</template>

<style scoped>
.page h1 {
  margin: 0 0 12px;
}

.meta {
  color: #8b9cb3;
  font-size: 13px;
  margin-bottom: 16px;
}

.block {
  margin-bottom: 24px;
}

.block h2 {
  font-size: 16px;
  margin: 0 0 12px;
}

.block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.card {
  background: #121820;
  border: 1px solid #243041;
  border-radius: 12px;
  padding: 14px;
}

.card-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.card h3 {
  margin: 0;
  font-size: 15px;
}

.desc {
  margin: 8px 0 0;
  font-size: 12px;
  color: #8b9cb3;
}

.badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 999px;
}

.badge.ok {
  background: #10261c;
  color: #7dffb2;
}

.badge.down {
  background: #261010;
  color: #ff8f8f;
}

.badge.unknown {
  background: #1a1a10;
  color: #ffd27d;
}

.links {
  margin: 10px 0 0;
  padding-left: 18px;
  font-size: 13px;
}

.links a {
  color: #93c5fd;
  word-break: break-all;
}

.copy {
  margin-left: 6px;
  font-size: 11px;
  border: 1px solid #314158;
  background: transparent;
  color: #8b9cb3;
  border-radius: 6px;
  padding: 2px 6px;
  cursor: pointer;
}

.creds {
  margin-top: 10px;
  font-size: 12px;
}

.creds ul {
  margin: 4px 0 0;
  padding-left: 18px;
}

.creds code {
  color: #dbe7ff;
}

.ok-text {
  color: #7dffb2;
}

.down-text {
  color: #ff8f8f;
}

.toggle {
  border: 1px solid #314158;
  background: #121820;
  color: #dbe7ff;
  border-radius: 8px;
  padding: 6px 10px;
  cursor: pointer;
  font-size: 12px;
}

.jf-lib {
  margin-top: 12px;
}

.jf-lib h3 {
  font-size: 13px;
  color: #8b9cb3;
  margin: 0 0 8px;
}

.table-wrap {
  overflow-x: auto;
  border: 1px solid #243041;
  border-radius: 8px;
}

table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12px;
}

th,
td {
  padding: 8px 10px;
  border-bottom: 1px solid #243041;
  text-align: left;
}

th {
  color: #8b9cb3;
  background: #0b1016;
}

.mono {
  font-family: ui-monospace, monospace;
  font-size: 11px;
}

.wrap {
  word-break: break-all;
  font-size: 12px;
  color: #8b9cb3;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}
</style>
