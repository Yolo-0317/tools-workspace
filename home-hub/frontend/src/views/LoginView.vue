<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { login } from '../auth/hubAuth'

const router = useRouter()
const route = useRoute()

const username = ref('')
const password = ref('')
const error = ref('')
const loading = ref(false)

async function onSubmit() {
  error.value = ''
  loading.value = true
  try {
    const state = await login(username.value.trim(), password.value)
    const redirect = String(route.query.redirect ?? '')
    if (state.shareOnly) {
      await router.replace('/selection')
      return
    }
    await router.replace(redirect && redirect !== '/login' ? redirect : '/')
  } catch (e) {
    error.value = e instanceof Error ? e.message : '登录失败'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="page">
    <form class="card" @submit.prevent="onSubmit">
      <h1>Home Hub</h1>
      <p class="sub">登录后访问看板</p>

      <label>
        用户名
        <input v-model="username" autocomplete="username" required />
      </label>
      <label>
        密码
        <input
          v-model="password"
          type="password"
          autocomplete="current-password"
          required
        />
      </label>

      <p v-if="error" class="error">{{ error }}</p>

      <button type="submit" :disabled="loading">
        {{ loading ? '登录中…' : '登录' }}
      </button>

      <p class="hint">管理员全功能 · 分享账号仅选股页</p>
    </form>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh;
  display: grid;
  place-items: center;
  background: #0f1419;
  color: #e7ecf3;
  padding: 24px;
}

.card {
  width: min(400px, 100%);
  display: flex;
  flex-direction: column;
  gap: 14px;
  padding: 28px 24px;
  border-radius: 16px;
  border: 1px solid #243041;
  background: #121820;
}

h1 {
  margin: 0;
  font-size: 22px;
}

.sub {
  margin: -6px 0 8px;
  color: #8b9cb3;
  font-size: 14px;
}

label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: #8b9cb3;
}

input {
  border-radius: 10px;
  border: 1px solid #314158;
  background: #0f1419;
  color: #e7ecf3;
  padding: 10px 12px;
  font: inherit;
}

input:focus {
  outline: 2px solid #2563eb;
  border-color: transparent;
}

button {
  margin-top: 4px;
  border: none;
  border-radius: 10px;
  padding: 11px 16px;
  background: #2563eb;
  color: #fff;
  font-weight: 600;
  cursor: pointer;
}

button:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.error {
  margin: 0;
  color: #ff8f8f;
  font-size: 13px;
}

.hint {
  margin: 0;
  color: #6b7c93;
  font-size: 12px;
  text-align: center;
}
</style>
