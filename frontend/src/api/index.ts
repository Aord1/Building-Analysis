import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// 响应拦截器
api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const message = error.response?.data?.detail || error.message
    return Promise.reject(new Error(message))
  }
)

// 健康检查
export const healthCheck = () => api.get('/health')

// 仪表盘
export const getDashboardStats = () => api.get('/dashboard/stats')
export const getInterestPoints = () => api.get('/dashboard/interest-points')
export const getRecommendations = () => api.get('/dashboard/recommendations')

// 笔记
export const getNotes = (params?: { page?: number; page_size?: number; sentiment?: string }) => 
  api.get('/notes', { params })
export const analyzeNote = (noteId: string) => api.post(`/notes/${noteId}/analyze`)

// 流水线
export const getPipelineStatus = () => api.get('/pipeline/status')
export const runPipeline = () => api.post('/pipeline/run')
export const resetPipeline = () => api.post('/pipeline/reset')

// 模型
export const getModels = () => api.get('/ml/models')
export const trainSVM = (data: { tune_hyperparams?: boolean; test_size?: number }) => 
  api.post('/ml/train/svm', data)
export const trainVLM = (data: { epochs?: number; batch_size?: number; learning_rate?: number }) => 
  api.post('/ml/train/vlm', data)
export const getModelMetrics = (modelName: string) => api.get(`/ml/models/${modelName}/metrics`)

// 上传
export const uploadImages = (files: FormData) => 
  api.post('/upload/images', files, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
export const uploadHtmlNotes = (file: FormData) => 
  api.post('/upload/notes/html', file, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })

export default api
