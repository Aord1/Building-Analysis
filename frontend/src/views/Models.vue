<template>
  <div class="models-page">
    <el-row :gutter="20">
      <!-- SVM 模型 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="model-header">
              <div class="model-title">
                <el-icon :size="24"><Cpu /></el-icon>
                <span>SVM 情感分析模型</span>
                <el-tag :type="svmModel?.exists ? 'success' : 'info'" size="small">
                  {{ svmModel?.exists ? '已训练' : '未训练' }}
                </el-tag>
              </div>
            </div>
          </template>

          <div class="model-info">
            <p><strong>模型类型:</strong> scikit-learn SVM + TF-IDF</p>
            <p><strong>模型大小:</strong> {{ svmModel?.size_mb?.toFixed(2) || 0 }} MB</p>
            <p><strong>模型路径:</strong> <code>{{ svmModel?.path || '-' }}</code></p>
          </div>

          <el-divider />

          <h4>训练参数</h4>
          <el-form :model="svmForm" label-width="120px">
            <el-form-item label="超参数调优">
              <el-switch v-model="svmForm.tune_hyperparams" />
            </el-form-item>
            <el-form-item label="测试集比例">
              <el-slider v-model="svmForm.test_size" :min="0.1" :max="0.5" :step="0.05" show-stops />
            </el-form-item>
          </el-form>

          <el-button 
            type="primary" 
            :loading="trainingSVM"
            @click="trainSVMModel"
            class="train-btn"
          >
            {{ svmModel?.exists ? '重新训练' : '开始训练' }}
          </el-button>

          <!-- 指标展示 -->
          <div v-if="svmMetrics" class="metrics-section">
            <el-divider />
            <h4>评估指标</h4>
            <el-row :gutter="10">
              <el-col :span="8">
                <div class="metric-card">
                  <div class="metric-value">{{ (svmMetrics.accuracy * 100).toFixed(1) }}%</div>
                  <div class="metric-label">准确率</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="metric-card">
                  <div class="metric-value">{{ (svmMetrics.f1_score * 100).toFixed(1) }}%</div>
                  <div class="metric-label">F1-Score</div>
                </div>
              </el-col>
              <el-col :span="8">
                <div class="metric-card">
                  <div class="metric-value">{{ svmMetrics.support }}</div>
                  <div class="metric-label">测试样本</div>
                </div>
              </el-col>
            </el-row>
          </div>
        </el-card>
      </el-col>

      <!-- VLM 模型 -->
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="model-header">
              <div class="model-title">
                <el-icon :size="24"><Picture /></el-icon>
                <span>轻量级 VLM 模型</span>
                <el-tag :type="vlmModel?.exists ? 'success' : 'info'" size="small">
                  {{ vlmModel?.exists ? '已训练' : '未训练' }}
                </el-tag>
              </div>
            </div>
          </template>

          <div class="model-info">
            <p><strong>模型类型:</strong> PyTorch ResNet18 + 分类头</p>
            <p><strong>模型大小:</strong> {{ vlmModel?.size_mb?.toFixed(2) || 0 }} MB</p>
            <p><strong>模型路径:</strong> <code>{{ vlmModel?.path || '-' }}</code></p>
          </div>

          <el-divider />

          <h4>训练参数</h4>
          <el-form :model="vlmForm" label-width="120px">
            <el-form-item label="训练轮数">
              <el-input-number v-model="vlmForm.epochs" :min="10" :max="200" />
            </el-form-item>
            <el-form-item label="批次大小">
              <el-input-number v-model="vlmForm.batch_size" :min="8" :max="128" :step="8" />
            </el-form-item>
            <el-form-item label="学习率">
              <el-input-number v-model="vlmForm.learning_rate" :min="1e-6" :max="1e-2" :step="1e-4" />
            </el-form-item>
          </el-form>

          <el-alert
            title="注意"
            description="VLM 训练需要准备标注数据集。当前版本仅支持配置参数，实际训练需准备数据。"
            type="warning"
            :closable="false"
            style="margin-bottom: 16px"
          />

          <el-button 
            type="primary" 
            :loading="trainingVLM"
            @click="trainVLMModel"
            class="train-btn"
          >
            {{ vlmModel?.exists ? '重新训练' : '开始训练' }}
          </el-button>
        </el-card>
      </el-col>
    </el-row>

    <!-- 模型对比 -->
    <el-card class="comparison-card">
      <template #header>
        <span>模型对比</span>
      </template>
      <el-table :data="modelComparison" stripe>
        <el-table-column prop="feature" label="特性" />
        <el-table-column prop="svm" label="SVM 情感分析">
          <template #default="{ row }">
            <el-tag :type="row.svmType || 'info'">{{ row.svm }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="vlm" label="轻量级 VLM">
          <template #default="{ row }">
            <el-tag :type="row.vlmType || 'info'">{{ row.vlm }}</el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Cpu, Picture } from '@element-plus/icons-vue'
import { getModels, trainSVM, trainVLM, getModelMetrics } from '../api'

const models = ref<any[]>([])
const trainingSVM = ref(false)
const trainingVLM = ref(false)
const svmMetrics = ref<any>(null)

const svmForm = ref({
  tune_hyperparams: true,
  test_size: 0.2
})

const vlmForm = ref({
  epochs: 50,
  batch_size: 32,
  learning_rate: 1e-4
})

const svmModel = computed(() => models.value.find(m => m.name === 'SVM_Sentiment'))
const vlmModel = computed(() => models.value.find(m => m.name === 'LightweightVLM'))

const modelComparison = computed(() => [
  { feature: '框架', svm: 'scikit-learn', vlm: 'PyTorch', svmType: 'success', vlmType: 'success' },
  { feature: '算法', svm: 'SVM + TF-IDF', vlm: 'ResNet18 + FC', svmType: '', vlmType: '' },
  { feature: '参数量', svm: '~10K', vlm: '~11M', svmType: 'success', vlmType: '' },
  { feature: '推理速度', svm: '< 10ms', vlm: '< 100ms', svmType: 'success', vlmType: 'success' },
  { feature: '训练数据', svm: '文本标注', vlm: '图片标注', svmType: '', vlmType: '' },
  { feature: '适用场景', svm: '情感分析', vlm: '图像分类', svmType: '', vlmType: '' },
])

const fetchModels = async () => {
  models.value = await getModels()
  
  // 加载 SVM 指标
  if (svmModel.value?.exists) {
    try {
      svmMetrics.value = await getModelMetrics('svm')
    } catch {
      svmMetrics.value = null
    }
  }
}

const trainSVMModel = async () => {
  trainingSVM.value = true
  try {
    const res: any = await trainSVM({
      tune_hyperparams: svmForm.value.tune_hyperparams,
      test_size: svmForm.value.test_size
    })
    ElMessage.success(`训练完成! 准确率: ${(res.metrics.accuracy * 100).toFixed(1)}%`)
    await fetchModels()
  } catch (e: any) {
    ElMessage.error(e.message || '训练失败')
  } finally {
    trainingSVM.value = false
  }
}

const trainVLMModel = async () => {
  trainingVLM.value = true
  try {
    await trainVLM({
      epochs: vlmForm.value.epochs,
      batch_size: vlmForm.value.batch_size,
      learning_rate: vlmForm.value.learning_rate
    })
    ElMessage.success('VLM 训练任务已启动')
    await fetchModels()
  } catch (e: any) {
    ElMessage.error(e.message || '训练失败')
  } finally {
    trainingVLM.value = false
  }
}

onMounted(fetchModels)
</script>

<style scoped>
.models-page {
  padding-bottom: 40px;
}

.model-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.model-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.model-info {
  color: #606266;
  font-size: 14px;
}

.model-info p {
  margin: 8px 0;
}

.model-info code {
  background: #f5f7fa;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.train-btn {
  width: 100%;
  margin-top: 16px;
}

.metrics-section {
  margin-top: 20px;
}

.metric-card {
  text-align: center;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
}

.metric-value {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.comparison-card {
  margin-top: 20px;
}
</style>
