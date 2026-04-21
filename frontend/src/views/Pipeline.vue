<template>
  <div class="pipeline">
    <!-- 页面标题 -->
    <el-page-header title="返回" content="分析流水线" />

    <!-- 功能卡片 -->
    <el-row :gutter="20" class="feature-row">
      <!-- HTML 提取 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><Document /></el-icon>
              <span>HTML 数据提取</span>
            </div>
          </template>

          <el-tabs v-model="extractTab">
            <el-tab-pane label="上传文件" name="upload">
              <el-upload
                drag
                action="/api/pipeline/extract/html"
                :on-success="handleExtractSuccess"
                :on-error="handleExtractError"
                accept=".html,.htm"
              >
                <el-icon class="el-icon--upload"><Upload /></el-icon>
                <div class="el-upload__text">
                  拖拽文件到此处或 <em>点击上传</em>
                </div>
              </el-upload>
            </el-tab-pane>

            <el-tab-pane label="文件夹路径" name="folder">
              <el-input
                v-model="folderPath"
                placeholder="输入 HTML 文件夹绝对路径"
              >
                <template #append>
                  <el-button @click="extractFromFolder">提取</el-button>
                </template>
              </el-input>
            </el-tab-pane>
          </el-tabs>

          <div v-if="extractionResult" class="result-preview">
            <el-divider />
            <h4>提取结果</h4>
            <el-descriptions :column="2" border>
              <el-descriptions-item label="文本数量">
                {{ extractionResult.stats?.text_count || extractionResult.stats?.total_texts || 0 }}
              </el-descriptions-item>
              <el-descriptions-item label="图片数量">
                {{ extractionResult.stats?.image_count || extractionResult.stats?.total_images || 0 }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </el-col>

      <!-- 分析控制 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <el-icon><VideoPlay /></el-icon>
              <span>分析控制</span>
            </div>
          </template>

          <div class="analysis-buttons">
            <el-button
              type="primary"
              size="large"
              @click="runNLPAnalysis"
              :loading="nlpLoading"
            >
              <el-icon><ChatLineRound /></el-icon>
              NLP 文本分析
            </el-button>

            <el-button
              type="success"
              size="large"
              @click="runVLMAnalysis"
              :loading="vlmLoading"
            >
              <el-icon><Picture /></el-icon>
              VLM 图像分析
            </el-button>

            <el-divider />

            <el-button
              type="warning"
              size="large"
              @click="runFullPipeline"
              :loading="fullLoading"
            >
              <el-icon><MagicStick /></el-icon>
              一键完整分析
            </el-button>
          </div>

          <!-- 状态显示 -->
          <div v-if="analyzerStatus.stage !== 'idle'" class="status-display">
            <el-divider />
            <h4>当前状态</h4>
            <el-progress
              :percentage="analyzerStatus.progress"
              :status="getProgressStatus"
            />
            <p class="status-message">{{ analyzerStatus.message }}</p>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 分析结果 -->
    <el-row :gutter="20" class="results-row">
      <el-col :span="24">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>分析结果</span>
              <el-button type="primary" size="small" @click="refreshResults">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </template>

          <el-tabs v-model="resultTab">
            <el-tab-pane label="NLP 结果" name="nlp">
              <div v-if="nlpResults.length" class="results-list">
                <el-table :data="nlpResults.slice(0, 10)" stripe>
                  <el-table-column prop="note_id" label="ID" width="120" />
                  <el-table-column prop="content" label="内容" show-overflow-tooltip>
                    <template #default="{ row }">
                      {{ row.content?.substring(0, 50) }}...
                    </template>
                  </el-table-column>
                  <el-table-column prop="sentiment_label" label="情感" width="100">
                    <template #default="{ row }">
                      <el-tag :type="getSentimentType(row.sentiment_label)">
                        {{ row.sentiment_label }}
                      </el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="sentiment_score" label="分数" width="100">
                    <template #default="{ row }">
                      {{ row.sentiment_score?.toFixed(2) }}
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="暂无 NLP 分析结果" />
            </el-tab-pane>

            <el-tab-pane label="VLM 结果" name="vlm">
              <div v-if="vlmResults.length" class="results-list">
                <el-table :data="vlmResults.slice(0, 10)" stripe>
                  <el-table-column prop="image_name" label="图片" />
                  <el-table-column prop="predicted_category" label="类别" width="120">
                    <template #default="{ row }">
                      <el-tag type="success">{{ row.predicted_category_zh || row.predicted_category }}</el-tag>
                    </template>
                  </el-table-column>
                  <el-table-column prop="confidence" label="置信度" width="120">
                    <template #default="{ row }">
                      {{ (row.confidence * 100).toFixed(1) }}%
                    </template>
                  </el-table-column>
                </el-table>
              </div>
              <el-empty v-else description="暂无 VLM 分析结果" />
            </el-tab-pane>

            <el-tab-pane label="统计摘要" name="summary">
              <el-descriptions :column="2" border v-if="summary">
                <el-descriptions-item label="分析文本数">{{ summary.texts_analyzed || 0 }}</el-descriptions-item>
                <el-descriptions-item label="分析图片数">{{ summary.images_analyzed || 0 }}</el-descriptions-item>
                <el-descriptions-item label="情感分布" :span="2">
                  <pre>{{ JSON.stringify(summary.sentiment_distribution, null, 2) }}</pre>
                </el-descriptions-item>
                <el-descriptions-item label="图片类别" :span="2">
                  <pre>{{ JSON.stringify(summary.image_categories, null, 2) }}</pre>
                </el-descriptions-item>
              </el-descriptions>
              <el-empty v-else description="暂无摘要数据" />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  extractHtmlFolder,
  analyzeNLP, analyzeVLM, runFullAnalysis,
  getAnalyzerStatus, getLatestResults
} from '../api/pipeline'

// 状态
const extractTab = ref('upload')
const resultTab = ref('nlp')
const folderPath = ref('')
const extractionResult = ref<any>(null)
const nlpLoading = ref(false)
const vlmLoading = ref(false)
const fullLoading = ref(false)
const analyzerStatus = ref({
  stage: 'idle',
  progress: 0,
  message: 'Ready'
})
const nlpResults = ref<any[]>([])
const vlmResults = ref<any[]>([])
const summary = ref<any>(null)

// 定时器
let statusTimer: number | null = null

// 计算属性
const getProgressStatus = computed(() => {
  if (analyzerStatus.value.stage === 'failed') return 'exception'
  if (analyzerStatus.value.progress === 100) return 'success'
  return ''
})

// 方法
const handleExtractSuccess = (response: any) => {
  extractionResult.value = response.results
  ElMessage.success(response.message)
}

const handleExtractError = (error: any) => {
  ElMessage.error('提取失败: ' + error.message)
}

const extractFromFolder = async () => {
  if (!folderPath.value) {
    ElMessage.warning('请输入文件夹路径')
    return
  }
  try {
    const res = await extractHtmlFolder(folderPath.value)
    extractionResult.value = res.results
    ElMessage.success(res.message)
  } catch (error: any) {
    ElMessage.error('提取失败: ' + error.message)
  }
}

const runNLPAnalysis = async () => {
  nlpLoading.value = true
  try {
    const res = await analyzeNLP()
    ElMessage.success(res.message)
    await refreshResults()
  } catch (error: any) {
    ElMessage.error('NLP 分析失败: ' + error.message)
  } finally {
    nlpLoading.value = false
  }
}

const runVLMAnalysis = async () => {
  vlmLoading.value = true
  try {
    const res = await analyzeVLM()
    ElMessage.success(res.message)
    await refreshResults()
  } catch (error: any) {
    ElMessage.error('VLM 分析失败: ' + error.message)
  } finally {
    vlmLoading.value = false
  }
}

const runFullPipeline = async () => {
  fullLoading.value = true
  try {
    await runFullAnalysis({
      source_path: null,
      skip_extraction: true
    })
    ElMessage.success('完整分析已启动')
    startStatusPolling()
  } catch (error: any) {
    ElMessage.error('启动失败: ' + error.message)
    fullLoading.value = false
  }
}

const refreshResults = async () => {
  try {
    const res = await getLatestResults()
    // 确保数据是数组类型
    if (res.results.nlp && Array.isArray(res.results.nlp)) {
      nlpResults.value = res.results.nlp
    }
    if (res.results.vlm && Array.isArray(res.results.vlm)) {
      vlmResults.value = res.results.vlm
    }
    if (res.results.unified && typeof res.results.unified === 'object' && 'summary' in res.results.unified) {
      summary.value = res.results.unified.summary
    }
  } catch (error) {
    console.error('刷新结果失败:', error)
  }
}

const startStatusPolling = () => {
  if (statusTimer) return
  statusTimer = window.setInterval(async () => {
    try {
      const status = await getAnalyzerStatus()
      analyzerStatus.value = status
      if (status.stage === 'completed' || status.stage === 'failed') {
        fullLoading.value = false
        stopStatusPolling()
        await refreshResults()
      }
    } catch (error) {
      console.error('获取状态失败:', error)
    }
  }, 2000)
}

const stopStatusPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
}

const getSentimentType = (label: string) => {
  const map: Record<string, string> = {
    'positive': 'success',
    'negative': 'danger',
    'neutral': 'info'
  }
  return map[label] || 'info'
}

// 生命周期
onMounted(() => {
  refreshResults()
})

onUnmounted(() => {
  stopStatusPolling()
})
</script>

<style scoped>
.pipeline {
  padding: 20px;
}

.feature-row {
  margin-top: 20px;
}

.results-row {
  margin-top: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-weight: bold;
}

.analysis-buttons {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.analysis-buttons .el-button {
  justify-content: flex-start;
}

.result-preview {
  margin-top: 16px;
}

.status-display {
  margin-top: 16px;
}

.status-message {
  text-align: center;
  color: #666;
  margin-top: 8px;
}

.results-list {
  max-height: 400px;
  overflow-y: auto;
}
</style>
