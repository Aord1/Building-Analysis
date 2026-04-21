<template>
  <div class="dashboard">
    <!-- 统计卡片 -->
    <el-row :gutter="20" class="stats-row">
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon blue">
            <el-icon><Document /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats?.total_notes || 0 }}</div>
            <div class="stat-label">笔记总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon green">
            <el-icon><Picture /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ stats?.total_images || 0 }}</div>
            <div class="stat-label">图片总数</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon orange">
            <el-icon><Star /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">{{ avgSentiment }}</div>
            <div class="stat-label">平均情感</div>
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-icon purple">
            <el-icon><Cpu /></el-icon>
          </div>
          <div class="stat-info">
            <div class="stat-value">
              <el-tag v-if="stats?.model_status?.svm" type="success" size="small">SVM</el-tag>
              <el-tag v-if="stats?.model_status?.vlm" type="success" size="small" class="ml-2">VLM</el-tag>
              <span v-if="!stats?.model_status?.svm && !stats?.model_status?.vlm">-</span>
            </div>
            <div class="stat-label">模型状态</div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="20" class="charts-row">
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>情感分布</span>
            </div>
          </template>
          <v-chart class="chart" :option="sentimentChartOption" autoresize />
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <template #header>
            <div class="card-header">
              <span>兴趣点 TOP10</span>
            </div>
          </template>
          <v-chart class="chart" :option="interestChartOption" autoresize />
        </el-card>
      </el-col>
    </el-row>

    <!-- 兴趣点列表 -->
    <el-card class="interest-card">
      <template #header>
        <div class="card-header">
          <span>热门兴趣点详情</span>
        </div>
      </template>
      <el-table :data="interestPoints" stripe>
        <el-table-column type="index" width="50" />
        <el-table-column prop="name" label="兴趣点" />
        <el-table-column prop="count" label="出现次数" width="120" sortable />
        <el-table-column label="平均情感" width="150">
          <template #default="{ row }">
            <el-tag :type="getSentimentType(row.avg_sentiment)">
              {{ row.avg_sentiment.toFixed(2) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="样例图片" width="300">
          <template #default="{ row }">
            <el-image
              v-for="img in row.images.slice(0, 3)"
              :key="img"
              :src="img"
              :preview-src-list="row.images"
              fit="cover"
              class="thumb-image"
            />
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- 建议 -->
    <el-card v-if="recommendations.length" class="recommendation-card">
      <template #header>
        <div class="card-header">
          <span>优化建议</span>
        </div>
      </template>
      <el-timeline>
        <el-timeline-item
          v-for="(rec, index) in recommendations"
          :key="index"
          :type="rec.type"
          :icon="getRecommendationIcon(rec.type)"
        >
          <h4>{{ rec.title }}</h4>
          <p>{{ rec.content }}</p>
        </el-timeline-item>
      </el-timeline>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import { PieChart, BarChart } from 'echarts/charts'
import {
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, ToolboxComponent
} from 'echarts/components'
import VChart from 'vue-echarts'
import { useDashboardStore } from '../stores/dashboard'
import { storeToRefs } from 'pinia'

use([
  CanvasRenderer, PieChart, BarChart,
  TitleComponent, TooltipComponent, LegendComponent,
  GridComponent, ToolboxComponent
])

const store = useDashboardStore()
const { stats, interestPoints, recommendations } = storeToRefs(store)

const avgSentiment = computed(() => {
  const val = stats?.value?.avg_sentiment || 0
  return val > 0 ? `+${val.toFixed(2)}` : val.toFixed(2)
})

const sentimentChartOption = computed(() => ({
  tooltip: { trigger: 'item' },
  legend: { bottom: '5%' },
  series: [{
    type: 'pie',
    radius: ['40%', '70%'],
    avoidLabelOverlap: false,
    itemStyle: {
      borderRadius: 10,
      borderColor: '#fff',
      borderWidth: 2
    },
    label: { show: false },
    data: store.sentimentChartData
  }]
}))

const interestChartOption = computed(() => ({
  tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
  grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
  xAxis: { type: 'value' },
  yAxis: {
    type: 'category',
    data: store.interestChartData.map(d => d.name).reverse()
  },
  series: [{
    type: 'bar',
    data: store.interestChartData.map(d => d.value).reverse(),
    itemStyle: { color: '#409eff', borderRadius: [0, 4, 4, 0] }
  }]
}))

const getSentimentType = (score: number) => {
  if (score > 0.2) return 'success'
  if (score < -0.2) return 'danger'
  return 'info'
}

const getRecommendationIcon = (type: string) => {
  const icons: Record<string, string> = {
    success: 'Check',
    warning: 'Warning',
    info: 'InfoFilled'
  }
  return icons[type] || 'InfoFilled'
}

onMounted(() => {
  store.fetchAll()
})
</script>

<style scoped>
.dashboard {
  padding-bottom: 40px;
}

.stats-row {
  margin-bottom: 20px;
}

.stat-card {
  display: flex;
  align-items: center;
  padding: 10px;
}

.stat-icon {
  width: 60px;
  height: 60px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  color: #fff;
  margin-right: 16px;
}

.stat-icon.blue { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }
.stat-icon.green { background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%); }
.stat-icon.orange { background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); }
.stat-icon.purple { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); }

.stat-value {
  font-size: 28px;
  font-weight: bold;
  color: #303133;
}

.stat-label {
  font-size: 14px;
  color: #909399;
  margin-top: 4px;
}

.charts-row {
  margin-bottom: 20px;
}

.chart {
  height: 300px;
}

.card-header {
  font-weight: bold;
}

.interest-card, .recommendation-card {
  margin-bottom: 20px;
}

.thumb-image {
  width: 80px;
  height: 60px;
  margin-right: 8px;
  border-radius: 4px;
}

.ml-2 {
  margin-left: 8px;
}
</style>
