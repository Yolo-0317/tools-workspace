import { createRouter, createWebHistory } from 'vue-router'
import AppShell from '../layouts/AppShell.vue'
import MobileShell from '../layouts/MobileShell.vue'

const router = createRouter({
  history: createWebHistory(),
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
        { path: '', name: 'home', component: () => import('../views/HomeView.vue') },
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
        {
          path: '',
          name: 'm-home',
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
