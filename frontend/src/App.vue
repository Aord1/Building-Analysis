<template>
  <el-container class="app-container">
    <el-aside width="220px" class="sidebar">
      <div class="logo">
        <el-icon :size="32"><HomeFilled /></el-icon>
        <span>古建筑分析</span>
      </div>
      <el-menu
        :default-active="$route.path"
        router
        class="nav-menu"
        background-color="#1a1a2e"
        text-color="#b8b8d1"
        active-text-color="#fff"
      >
        <el-menu-item index="/">
          <el-icon><DataLine /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>
        <el-menu-item index="/notes">
          <el-icon><Document /></el-icon>
          <span>笔记管理</span>
        </el-menu-item>
        <el-menu-item index="/images">
          <el-icon><Picture /></el-icon>
          <span>图片分析</span>
        </el-menu-item>
        <el-menu-item index="/pipeline">
          <el-icon><VideoPlay /></el-icon>
          <span>分析流水线</span>
        </el-menu-item>
        <el-menu-item index="/models">
          <el-icon><Cpu /></el-icon>
          <span>模型管理</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <h2>{{ $route.meta.title || '仪表盘' }}</h2>
        </div>
        <div class="header-right">
          <el-tag :type="apiStatus.type" effect="dark">
            {{ apiStatus.text }}
          </el-tag>
        </div>
      </el-header>
      
      <el-main class="main-content">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { healthCheck } from './api'

const apiStatus = ref({ type: 'info' as const, text: '检查中...' } as { type: 'info' | 'success' | 'danger', text: string })

onMounted(async () => {
  try {
    await healthCheck()
    apiStatus.value = { type: 'success', text: 'API 正常' }
  } catch {
    apiStatus.value = { type: 'danger', text: 'API 离线' }
  }
})
</script>

<style scoped>
.app-container {
  height: 100vh;
}

.sidebar {
  background: #1a1a2e;
  color: #fff;
}

.logo {
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid #2d2d44;
}

.nav-menu {
  border-right: none;
}

.header {
  background: #fff;
  box-shadow: 0 2px 8px rgba(0,0,0,0.1);
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.header-left h2 {
  margin: 0;
  color: #333;
}

.main-content {
  background: #f5f7fa;
  padding: 20px;
}

.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
