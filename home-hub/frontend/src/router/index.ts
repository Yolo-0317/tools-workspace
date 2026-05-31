import { createRouter, createWebHistory } from 'vue-router'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'home', component: () => import('../views/HomeView.vue') },
    { path: '/portfolio', name: 'portfolio', component: () => import('../views/PortfolioView.vue') },
    { path: '/selection', name: 'selection', component: () => import('../views/SelectionView.vue') },
    { path: '/monitor', name: 'monitor', component: () => import('../views/MonitorView.vue') },
    { path: '/jobs', name: 'jobs', component: () => import('../views/JobsView.vue') },
    { path: '/services', name: 'services', component: () => import('../views/ServicesView.vue') },
    { path: '/chat', name: 'chat', component: () => import('../views/ChatView.vue') },
  ],
})

export default router
