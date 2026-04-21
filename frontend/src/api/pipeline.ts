import api from './index'

// ==================== 类型定义 ====================

/** API 通用响应 */
export interface ApiResponse<T = unknown> {
  success: boolean
  message: string
  results?: T
}

/** 提取结果统计 */
export interface ExtractionStats {
  text_count?: number
  image_count?: number
  file_count?: number
  total_texts?: number
  total_images?: number
}

/** 提取结果 */
export interface ExtractionResult {
  source_file?: string
  source_files?: string[]
  texts: unknown[]
  images: unknown[]
  stats: ExtractionStats
}

/** 分析器状态 */
export interface AnalyzerStatus {
  stage: 'idle' | 'extraction' | 'nlp_analysis' | 'vlm_analysis' | 'completed' | 'failed'
  progress: number
  message: string
}

/** NLP 分析结果 */
export interface NLPResult {
  total: number
  summary?: {
    distribution: Record<string, number>
    avg_score?: number
    avg_confidence?: number
  }
  output_path?: string
}

/** VLM 分析结果 */
export interface VLMResult {
  total: number
  categories?: Record<string, number>
  output_path?: string
}

/** 完整分析请求 */
export interface FullAnalysisRequest {
  source_path?: string | null
  skip_extraction?: boolean
}

// ==================== HTML 提取 ====================

/**
 * 上传 HTML 文件提取文本和图片
 * @param file - HTML 文件
 */
export function extractHtml(file: File): Promise<ApiResponse<ExtractionResult>> {
  const formData = new FormData()
  formData.append('file', file)
  return api.post('/pipeline/extract/html', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}

/**
 * 从文件夹批量提取 HTML 数据
 * @param folderPath - 文件夹绝对路径
 */
export function extractHtmlFolder(folderPath: string): Promise<ApiResponse<ExtractionResult>> {
  return api.post('/pipeline/extract/html/folder', null, {
    params: { folder_path: folderPath }
  })
}

// ==================== 分析接口 ====================

/** 使用 NLP 分析已提取的文本 */
export function analyzeNLP(): Promise<ApiResponse<NLPResult>> {
  return api.post('/pipeline/analyze/nlp')
}

/** 使用 VLM 分析已提取的图片 */
export function analyzeVLM(): Promise<ApiResponse<VLMResult>> {
  return api.post('/pipeline/analyze/vlm')
}

/**
 * 运行完整分析流水线
 * @param data - 分析请求参数
 */
export function runFullAnalysis(data: FullAnalysisRequest): Promise<ApiResponse<unknown>> {
  return api.post('/pipeline/analyze/full', data)
}

// ==================== 状态查询 ====================

/** 获取分析器当前状态 */
export function getAnalyzerStatus(): Promise<AnalyzerStatus> {
  return api.get('/pipeline/analyzer/status')
}

/** 获取最新的分析结果 */
export function getLatestResults(): Promise<{
  available_results: string[]
  results: Record<string, unknown>
}> {
  return api.get('/pipeline/results/latest')
}

// ==================== 原有接口（兼容）====================

/** 获取流水线状态 */
export function getPipelineStatus(): Promise<AnalyzerStatus> {
  return api.get('/pipeline/status')
}

/** 启动传统分析流水线 */
export function runPipeline(): Promise<ApiResponse<unknown>> {
  return api.post('/pipeline/run')
}

/** 重置流水线状态 */
export function resetPipeline(): Promise<ApiResponse<unknown>> {
  return api.post('/pipeline/reset')
}
