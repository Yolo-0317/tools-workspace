import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import ElementPlus from "element-plus";
import "element-plus/dist/index.css";
import "./style.css";
import App from "./App.vue";
const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: "/", component: () => import("./views/CastView.vue") },
    {
      path: "/readings/:id",
      component: () => import("./views/ReadingView.vue"),
    },
    { path: "/history", component: () => import("./views/HistoryView.vue") },
    {
      path: "/classics/:id?",
      component: () => import("./views/ClassicsView.vue"),
    },
    { path: "/:pathMatch(.*)*", redirect: "/" },
  ],
});
createApp(App).use(router).use(ElementPlus).mount("#app");
