<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import {
  fetchJellyfinMappings,
  fetchServicesCatalog,
  healthClass,
  healthLabel,
} from '../api/services'
import type { JellyfinMappings, ServiceCategory, ServiceItem } from '../types/services'

const categories = ref<ServiceCategory[]>([])
const domains = ref<Record<string, unknown>>({})
const dockerRunning = ref<string[]>([])
const jellyfin = ref<JellyfinMappings | null>(null)
const error = ref('')
const loading = ref(true)
const showJellyfin = ref(false)
const showDocker = ref(true)
const dockerFilter = ref('')

/** catalog docker_container → service display name */
const catalogByContainer = computed(() => {
  const map = new Map<string, ServiceItem>()
  for (const cat of categories.value) {
    for (const item of cat.items) {
      if (item.docker_container) {
        map.set(item.docker_container, item)
      }
    }
  }
  return map
})

const dockerKnown = computed(() => {
  const out: Array<{ name: string; container: string; up: boolean }> = []
  for (const [container, item] of catalogByContainer.value) {
    out.push({
      name: item.name,
      container,
      up: dockerRunning.value.includes(container),
    })
  }
  return out.sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
})

const dockerOther = computed(() => {
  const known = new Set(catalogByContainer.value.keys())
  return dockerRunning.value
    .filter((c) => !known.has(c))
    .sort((a, b) => a.localeCompare(b))
})

const dockerFilteredOther = computed(() => {
  const q = dockerFilter.value.trim().toLowerCase()
  if (!q) return dockerOther.value
  return dockerOther.value.filter((c) => c.toLowerCase().includes(q))
})

const dockerCatalogUp = computed(
  () => dockerKnown.value.filter((x) => x.up).length,
)

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

    <section class="block docker-block">
      <div class="block-head">
        <div class="docker-title">
          <h2>Docker</h2>
          <span class="docker-count">{{ dockerRunning.length }} 个运行中</span>
        </div>
        <button type="button" class="toggle" @click="showDocker = !showDocker">
          {{ showDocker ? '收起' : '展开' }}
        </button>
      </div>

      <template v-if="showDocker">
        <p v-if="!dockerRunning.length" class="hint">当前无运行中的容器</p>
        <template v-else>
          <div class="docker-stats">
            <span class="stat">
              <span class="stat-dot up" />
              目录已登记 {{ dockerCatalogUp }}/{{ dockerKnown.length }}
            </span>
            <span v-if="dockerOther.length" class="stat muted">
              其它 {{ dockerOther.length }}
            </span>
            <button
              type="button"
              class="copy"
              @click="copyText(dockerRunning.join('\n'))"
            >
              复制全部
            </button>
          </div>

          <div v-if="dockerKnown.length" class="docker-group">
            <h3 class="docker-group-title">已登记服务</h3>
            <ul class="docker-chips">
              <li
                v-for="row in dockerKnown"
                :key="row.container"
                class="chip"
                :class="row.up ? 'chip-up' : 'chip-down'"
              >
                <span class="chip-name">{{ row.name }}</span>
                <span class="chip-container mono">{{ row.container }}</span>
                <span class="chip-status">{{ row.up ? '运行中' : '未运行' }}</span>
              </li>
            </ul>
          </div>

          <div v-if="dockerOther.length" class="docker-group">
            <div class="docker-group-head">
              <h3 class="docker-group-title">其它容器</h3>
              <input
                v-if="dockerOther.length > 6"
                v-model="dockerFilter"
                type="search"
                class="docker-search"
                placeholder="筛选容器名…"
                autocomplete="off"
              />
            </div>
            <ul v-if="dockerFilteredOther.length" class="docker-chips docker-chips-other">
              <li
                v-for="name in dockerFilteredOther"
                :key="name"
                class="chip chip-other"
              >
                <span class="chip-container mono">{{ name }}</span>
                <button
                  type="button"
                  class="copy chip-copy"
                  title="复制容器名"
                  @click="copyText(name)"
                >
                  复制
                </button>
              </li>
            </ul>
            <p v-else class="hint">无匹配「{{ dockerFilter }}」的容器</p>
          </div>
        </template>
      </template>
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

.docker-block .block-head {
  margin-bottom: 10px;
}

.docker-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.docker-title h2 {
  margin: 0;
}

.docker-count {
  font-size: 12px;
  color: #7dffb2;
  background: #10261c;
  padding: 2px 10px;
  border-radius: 999px;
}

.docker-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 12px 16px;
  margin-bottom: 14px;
  font-size: 12px;
  color: #8b9cb3;
}

.stat {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.stat.muted {
  color: #6b7d94;
}

.stat-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.stat-dot.up {
  background: #7dffb2;
  box-shadow: 0 0 6px #7dffb266;
}

.docker-group {
  margin-bottom: 16px;
}

.docker-group:last-child {
  margin-bottom: 0;
}

.docker-group-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 8px;
}

.docker-group-title {
  margin: 0;
  font-size: 12px;
  font-weight: 600;
  color: #8b9cb3;
  letter-spacing: 0.02em;
}

.docker-search {
  flex: 1;
  max-width: 200px;
  min-width: 120px;
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid #314158;
  border-radius: 8px;
  background: #0b1016;
  color: #dbe7ff;
}

.docker-search::placeholder {
  color: #6b7d94;
}

.docker-chips {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: 8px;
}

.docker-chips-other {
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
}

.chip {
  display: grid;
  grid-template-columns: 1fr auto;
  grid-template-rows: auto auto;
  gap: 2px 8px;
  align-items: start;
  padding: 10px 12px;
  border-radius: 10px;
  border: 1px solid #243041;
  background: #121820;
}

.chip-up {
  border-color: #1e3d2e;
  background: linear-gradient(135deg, #121820 0%, #0f1a14 100%);
}

.chip-down {
  border-color: #3d1e1e;
  opacity: 0.85;
}

.chip-other {
  grid-template-columns: 1fr auto;
  grid-template-rows: 1fr;
  align-items: center;
  background: #0f1419;
}

.chip-name {
  grid-column: 1;
  font-size: 13px;
  font-weight: 500;
  color: #e7ecf3;
}

.chip-container {
  grid-column: 1;
  font-size: 11px;
  color: #6b7d94;
  word-break: break-all;
}

.chip-other .chip-container {
  color: #8b9cb3;
}

.chip-status {
  grid-column: 2;
  grid-row: 1 / span 2;
  align-self: center;
  font-size: 10px;
  padding: 2px 7px;
  border-radius: 999px;
  white-space: nowrap;
}

.chip-up .chip-status {
  background: #10261c;
  color: #7dffb2;
}

.chip-down .chip-status {
  background: #261010;
  color: #ff8f8f;
}

.chip-copy {
  margin: 0;
}

.hint {
  color: #8b9cb3;
}

.error {
  color: #ff8f8f;
}
</style>
