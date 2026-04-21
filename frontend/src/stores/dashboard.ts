import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getDashboardStats, getInterestPoints, getRecommendations } from '../api'

export const useDashboardStore = defineStore('dashboard', () => {
  // State
  const stats = ref<any>(null)
  const interestPoints = ref<any[]>([])
  const recommendations = ref<any[]>([])
  const loading = ref(false)

  // Getters
  const sentimentChartData = computed(() => {
    if (!stats.value?.sentiment_distribution) return []
    const dist = stats.value.sentiment_distribution
    return [
      { name: '正面', value: dist.positive || 0, itemStyle: { color: '#67c23a' } },
      { name: '中性', value: dist.neutral || 0, itemStyle: { color: '#909399' } },
      { name: '负面', value: dist.negative || 0, itemStyle: { color: '#f56c6c' } },
    ]
  })

  const interestChartData = computed(() => {
    if (!stats.value?.interest_distribution) return []
    const dist = stats.value.interest_distribution
    return Object.entries(dist)
      .map(([name, value]) => ({ name, value }))
      .sort((a, b) => (b.value as number) - (a.value as number))
      .slice(0, 10)
  })

  // Actions
  const fetchStats = async () => {
    loading.value = true
    try {
      stats.value = await getDashboardStats()
    } finally {
      loading.value = false
    }
  }

  const fetchInterestPoints = async () => {
    const res: any = await getInterestPoints()
    interestPoints.value = res || []
  }

  const fetchRecommendations = async () => {
    const res: any = await getRecommendations()
    recommendations.value = res?.recommendations || []
  }

  const fetchAll = async () => {
    loading.value = true
    try {
      await Promise.all([
        fetchStats(),
        fetchInterestPoints(),
        fetchRecommendations()
      ])
    } finally {
      loading.value = false
    }
  }

  return {
    stats,
    interestPoints,
    recommendations,
    loading,
    sentimentChartData,
    interestChartData,
    fetchStats,
    fetchInterestPoints,
    fetchRecommendations,
    fetchAll
  }
})
