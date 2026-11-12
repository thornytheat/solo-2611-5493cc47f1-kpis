import { createRouter, createWebHistory } from 'vue-router'
import { setupGuards } from './guards'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', redirect: '/matrix' },
    {
      path: '/login',
      name: 'login',
      component: () => import('../pages/LoginPage.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/matrix',
      name: 'matrix',
      component: () => import('../pages/MatrixPage.vue'),
      meta: { title: '留存矩阵' },
    },
    {
      path: '/imports',
      name: 'imports',
      component: () => import('../pages/ImportPage.vue'),
      meta: { title: '订单导入' },
    },
    {
      path: '/cohorts/:month',
      name: 'cohort-detail',
      component: () => import('../pages/CohortDetailPage.vue'),
      meta: { title: '同期群详情' },
    },
    {
      path: '/ltv',
      name: 'ltv',
      component: () => import('../pages/LtvPage.vue'),
      meta: { title: 'LTV 测算' },
    },
    {
      path: '/channels',
      name: 'channels',
      component: () => import('../pages/ChannelsPage.vue'),
      meta: { title: '渠道对比' },
    },
    { path: '/:pathMatch(.*)*', redirect: '/matrix' },
  ],
  scrollBehavior: () => ({ top: 0 }),
})

setupGuards(router)

export default router
