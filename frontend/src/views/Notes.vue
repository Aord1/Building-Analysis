<template>
  <div class="notes-page">
    <el-card>
      <template #header>
        <div class="header-actions">
          <span>笔记列表</span>
          <div>
            <el-upload
              class="upload-inline"
              :action="''"
              :auto-upload="false"
              :on-change="handleHtmlUpload"
              accept=".html"
              :show-file-list="false"
            >
              <el-button type="primary" :icon="Upload">导入 HTML</el-button>
            </el-upload>
            <el-button 
              type="success" 
              :icon="Refresh"
              :loading="analyzingAll"
              @click="analyzeAll"
            >
              批量分析
            </el-button>
          </div>
        </div>
      </template>

      <el-table :data="notes" v-loading="loading" stripe>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="note-detail">
              <p><strong>完整内容:</strong></p>
              <p>{{ row.content }}</p>
              <el-divider />
              <p><strong>图片:</strong> {{ row.images?.length || 0 }} 张</p>
              <div class="image-list">
                <el-image
                  v-for="img in row.images"
                  :key="img"
                  :src="img"
                  fit="cover"
                  class="detail-image"
                />
              </div>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="title" label="标题" min-width="200" show-overflow-tooltip />
        <el-table-column prop="content" label="内容预览" min-width="300" show-overflow-tooltip>
          <template #default="{ row }">
            {{ row.content?.substring(0, 100) }}...
          </template>
        </el-table-column>
        <el-table-column label="情感" width="120">
          <template #default="{ row }">
            <el-tag :type="getSentimentType(row.sentiment_label)">
              {{ getSentimentText(row.sentiment_label) }}
              <span v-if="row.sentiment_score">({{ row.sentiment_score.toFixed(2) }})</span>
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="图片数" width="100">
          <template #default="{ row }">
            <el-tag type="info">{{ row.images?.length || 0 }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button 
              size="small" 
              @click="analyzeNote(row.id)"
              :loading="analyzingId === row.id"
            >
              分析
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="page"
        v-model:page-size="pageSize"
        :total="total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        class="pagination"
        @change="fetchNotes"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Upload, Refresh } from '@element-plus/icons-vue'
import { getNotes, analyzeNote as apiAnalyzeNote, uploadHtmlNotes } from '../api'

const notes = ref<any[]>([])
const loading = ref(false)
const analyzingId = ref<string | null>(null)
const analyzingAll = ref(false)
const page = ref(1)
const pageSize = ref(20)
const total = ref(0)

const fetchNotes = async () => {
  loading.value = true
  try {
    const res: any = await getNotes({
      page: page.value,
      page_size: pageSize.value
    })
    notes.value = res.items || []
    total.value = res.total || 0
  } finally {
    loading.value = false
  }
}

const analyzeNote = async (id: string) => {
  analyzingId.value = id
  try {
    await apiAnalyzeNote(id)
    ElMessage.success('分析完成')
    fetchNotes()
  } catch (e: any) {
    ElMessage.error(e.message || '分析失败')
  } finally {
    analyzingId.value = null
  }
}

const analyzeAll = async () => {
  analyzingAll.value = true
  try {
    for (const note of notes.value) {
      if (!note.sentiment_score) {
        await apiAnalyzeNote(note.id)
      }
    }
    ElMessage.success('批量分析完成')
    fetchNotes()
  } catch (e: any) {
    ElMessage.error(e.message || '批量分析失败')
  } finally {
    analyzingAll.value = false
  }
}

const handleHtmlUpload = async (file: any) => {
  const formData = new FormData()
  formData.append('file', file.raw)
  try {
    const res: any = await uploadHtmlNotes(formData)
    ElMessage.success(`成功导入 ${res.count} 条笔记`)
    fetchNotes()
  } catch (e: any) {
    ElMessage.error(e.message || '导入失败')
  }
}

const getSentimentType = (label?: string) => {
  const types: Record<string, string> = {
    positive: 'success',
    neutral: 'info',
    negative: 'danger'
  }
  return types[label || ''] || 'info'
}

const getSentimentText = (label?: string) => {
  const texts: Record<string, string> = {
    positive: '正面',
    neutral: '中性',
    negative: '负面'
  }
  return texts[label || ''] || '未分析'
}

onMounted(fetchNotes)
</script>

<style scoped>
.notes-page {
  padding-bottom: 40px;
}

.header-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.upload-inline {
  display: inline-block;
  margin-right: 12px;
}

.note-detail {
  padding: 20px;
  background: #f5f7fa;
  border-radius: 8px;
}

.image-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-top: 12px;
}

.detail-image {
  width: 120px;
  height: 90px;
  border-radius: 4px;
}

.pagination {
  margin-top: 20px;
  justify-content: flex-end;
}
</style>
