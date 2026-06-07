import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import MobileShell from '../layouts/MobileShell.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
      meta: { public: true },
    },
    {
      path: '/',
      component: AppShell,
      children: [
        { path: '', redirect: { name: 'advisor' } },
        {
          path: 'advisor',
          name: 'advisor',
          component: () => import('../views/HomeView.vue'),
        },
        {
          path: 'portfolio',
          name: 'portfolio',
          component: () => import('../views/PortfolioView.vue'),
        },
        {
          path: 'selection',
          name: 'selection',
          component: () => import('../views/SelectionView.vue'),
        },
        {
          path: 'monitor',
          name: 'monitor',
          component: () => import('../views/MonitorView.vue'),
        },
        {
          path: 'news',
          name: 'news',
          component: () => import('../views/NewsView.vue'),
          meta: { public: true, feature: 'news' },
        },
        {
          path: 'emotion',
          name: 'emotion',
          component: () => import('../views/EmotionCycleView.vue'),
        },
        { path: 'jobs', name: 'jobs', component: () => import('../views/JobsView.vue') },
        {
          path: 'services',
          name: 'services',
          component: () => import('../views/ServicesView.vue'),
        },
      ],
    },
    {
      path: '/m',
      component: MobileShell,
      meta: { mobile: true },
      children: [
        { path: '', redirect: { name: 'm-advisor' } },
        {
          path: 'advisor',
          name: 'm-advisor',
          component: () => import('../views/HomeView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'portfolio',
          name: 'm-portfolio',
          component: () => import('../views/PortfolioView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'selection',
          name: 'm-selection',
          component: () => import('../views/SelectionView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'monitor',
          name: 'm-monitor',
          component: () => import('../views/MonitorView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'news',
          name: 'm-news',
          component: () => import('../views/NewsView.vue'),
          meta: { mobile: true, public: true },
        },
        {
          path: 'emotion',
          name: 'm-emotion',
          component: () => import('../views/EmotionCycleView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'jobs',
          name: 'm-jobs',
          component: () => import('../views/JobsView.vue'),
          meta: { mobile: true },
        },
        {
          path: 'services',
          name: 'm-services',
          component: () => import('../views/ServicesView.vue'),
          meta: { mobile: true },
        },
      ],
    },
  ],
})

export default router
