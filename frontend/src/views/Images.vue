<template>
  <div class="images-page">
    <el-row :gutter="20">
      <!-- 上传区域 -->
      <el-col :span="8">
        <el-card>
          <template #header>
            <span>上传图片</span>
          </template>
          <el-upload
            drag
            :auto-upload="false"
            :on-change="handleFileChange"
            :file-list="fileList"
            multiple
            accept="image/*"
            class="upload-area"
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              拖拽文件到此处或 <em>点击上传</em>
            </div>
          </el-upload>
          <el-button 
            type="primary" 
            :loading="uploading"
            :disabled="!fileList.length"
            @click="submitUpload"
            class="upload-btn"
          >
            开始上传 ({{ fileList.length }})
          </el-button>
        </el-card>

        <!-- 分类统计 -->
        <el-card class="stats-card">
          <template #header>
            <span>分类统计</span>
          </template>
          <div v-for="(count, label) in labelStats" :key="label" class="stat-item">
            <span>{{ label }}</span>
            <el-tag type="primary">{{ count }}</el-tag>
          </div>
        </el-card>
      </el-col>

      <!-- 图片列表 -->
      <el-col :span="16">
        <el-card>
          <template #header>
            <div class="header-actions">
              <span>图片库 ({{ images.length }})</span>
              <el-input
                v-model="searchQuery"
                placeholder="搜索标签..."
                prefix-icon="Search"
                clearable
                style="width: 200px"
              />
            </div>
          </template>

          <div class="image-grid">
            <div 
              v-for="img in filteredImages" 
              :key="img.image_path"
              class="image-item"
            >
              <el-image
                :src="img.image_path"
                fit="cover"
                :preview-src-list="previewList"
                class="grid-image"
              />
              <div class="image-info">
                <div class="image-labels">
                  <el-tag 
                    v-for="label in img.labels" 
                    :key="label"
                    size="small"
                    effect="dark"
                  >
                    {{ label }}
                  </el-tag>
                  <span v-if="!img.labels?.length" class="no-label">未分类</span>
                </div>
                <div class="image-meta">
                  <el-tag v-if="img.confidence" type="info" size="small">
                    置信度: {{ (img.confidence * 100).toFixed(1) }}%
                  </el-tag>
                </div>
              </div>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { UploadFilled, Search } from '@element-plus/icons-vue'
import { uploadImages } from '../api'

const images = ref<any[]>([])
const fileList = ref<any[]>([])
const uploading = ref(false)
const searchQuery = ref('')

const filteredImages = computed(() => {
  if (!searchQuery.value) return images.value
  const query = searchQuery.value.toLowerCase()
  return images.value.filter(img => 
    img.labels?.some((l: string) => l.toLowerCase().includes(query))
  )
})

const previewList = computed(() => images.value.map(img => img.image_path))

const labelStats = computed(() => {
  const stats: Record<string, number> = {}
  images.value.forEach(img => {
    img.labels?.forEach((label: string) => {
      stats[label] = (stats[label] || 0) + 1
    })
  })
  return Object.fromEntries(
    Object.entries(stats).sort((a, b) => b[1] - a[1])
  )
})

const handleFileChange = (file: any, files: any[]) => {
  fileList.value = files
}

const submitUpload = async () => {
  if (!fileList.value.length) return
  
  uploading.value = true
  const formData = new FormData()
  fileList.value.forEach(file => {
    formData.append('files', file.raw)
  })
  
  try {
    const res: any = await uploadImages(formData)
    ElMessage.success(`成功上传 ${res.files?.length || 0} 张图片`)
    fileList.value = []
    fetchImages()
  } catch (e: any) {
    ElMessage.error(e.message || '上传失败')
  } finally {
    uploading.value = false
  }
}

const fetchImages = async () => {
  // 从 manifest 加载
  try {
    const res = await fetch('/api/dashboard/stats')
    const data = await res.json()
    // 实际应该从专门的图片 API 获取
    images.value = []
  } catch {
    images.value = []
  }
}

onMounted(fetchImages)
</script>

<style scoped>
.images-page {
  padding-bottom: 40px;
}

.upload-area {
  width: 100%;
}

.upload-btn {
  width: 100%;
  margin-top: 16px;
}

.stats-card {
  margin-top: 20px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
  border-bottom: 1px solid #ebeef5;
}

.stat-item:last-child {
  border-bottom: none;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
}

.image-item {
  border: 1px solid #ebeef5;
  border-radius: 8px;
  overflow: hidden;
  transition: box-shadow 0.3s;
}

.image-item:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
}

.grid-image {
  width: 100%;
  height: 150px;
}

.image-info {
  padding: 12px;
}

.image-labels {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin-bottom: 8px;
}

.no-label {
  color: #909399;
  font-size: 12px;
}

.image-meta {
  font-size: 12px;
  color: #606266;
}
</style>
