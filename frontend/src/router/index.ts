import { createRouter, createWebHistory } from 'vue-router'
import Dashboard from '../views/Dashboard.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/',
      name: 'Dashboard',
      component: Dashboard,
      meta: { title: '数据仪表盘' }
    },
    {
      path: '/notes',
      name: 'Notes',
      component: () => import('../views/Notes.vue'),
      meta: { title: '笔记管理' }
    },
    {
      path: '/images',
      name: 'Images',
      component: () => import('../views/Images.vue'),
      meta: { title: '图片分析' }
    },
    {
      path: '/pipeline',
      name: 'Pipeline',
      component: () => import('../views/Pipeline.vue'),
      meta: { title: '分析流水线' }
    },
    {
      path: '/models',
      name: 'Models',
      component: () => import('../views/Models.vue'),
      meta: { title: '模型管理' }
    }
  ]
})

export default router
