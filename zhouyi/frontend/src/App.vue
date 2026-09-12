<script setup lang="ts">
import zhCn from "element-plus/es/locale/lang/zh-cn";
</script>
<template>
  <el-config-provider :locale="zhCn"
    ><div class="app-shell">
      <header class="site-header">
        <router-link to="/" class="brand"
          >观易<span>一事一问</span></router-link
        >
        <nav aria-label="主导航">
          <router-link to="/" :class="{ active: $route.path === '/' }"
            >起卦</router-link
          ><router-link to="/history" active-class="active"
            >问卦记录</router-link
          ><router-link
            to="/classics"
            :class="{ active: $route.path.startsWith('/classics') }"
            >原典</router-link
          >
        </nav>
      </header>
      <main><router-view :key="$route.path" /></main>
      <footer>
        <span>观易 · 读其辞，观其变</span><span>不替你决定，助你看清。</span>
      </footer>
    </div></el-config-provider
  >
</template>
