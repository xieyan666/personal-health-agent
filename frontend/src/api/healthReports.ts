import { request } from './request'

export type ParseStatus = 'uploaded' | 'parsing' | 'parsed' | 'failed'
export interface HealthCheckIndicator { id: string; category: string; code: string; item_name: string; value: number; value_text?: string | null; unit?: string | null; reference_min?: number | null; reference_max?: number | null; reference_text?: string | null; flag: 'normal' | 'high' | 'low' | 'unknown'; source_page?: number | null; source_type: 'text' | 'table' | 'ocr' | 'image'; confidence?: number | null }
export interface HealthCheckReport { id: string; report_name: string; hospital?: string | null; report_date: string; file_name?: string | null; parse_status: ParseStatus; parse_progress: number; parse_error?: string | null; parse_mode?: 'TEXT' | 'TEXT_TABLE' | 'OCR_TABLE' | 'HYBRID' | null; ocr_used: boolean; parse_warnings: string[]; parsed_at?: string | null; created_at: string; updated_at: string; indicators: HealthCheckIndicator[] }
export interface HealthCheckReportCreate { report_name: string; hospital?: string; report_date: string; indicators: Omit<HealthCheckIndicator, 'id' | 'flag'>[] }

export const getHealthCheckReports = () => request.get<HealthCheckReport[]>('/health-reports').then(r => r.data)
export const getHealthCheckReport = (id: string) => request.get<HealthCheckReport>(`/health-reports/${id}`).then(r => r.data)
export const getHealthCheckReportItems = (id: string) => request.get<{ report_id: string; parse_status: ParseStatus; parse_progress: number; parse_error?: string | null; parse_mode?: string | null; ocr_used: boolean; warnings: string[]; items: HealthCheckIndicator[] }>(`/health-reports/${id}/items`).then(r => r.data)
export const createHealthCheckReport = (data: HealthCheckReportCreate) => request.post<HealthCheckReport>('/health-reports', data).then(r => r.data)
export const uploadHealthCheckReport = (file: File) => { const data = new FormData(); data.append('file', file); return request.post<HealthCheckReport>('/health-reports/upload', data, { headers: { 'Content-Type': 'multipart/form-data' } }).then(r => r.data) }
export const restartHealthCheckReportParsing = (id: string) => request.post<HealthCheckReport>(`/health-reports/${id}/parse`).then(r => r.data)
export const previewHealthCheckReport = (id: string) => request.get<Blob>(`/health-reports/${id}/file`, { responseType: 'blob' }).then(r => r.data)

export interface ReportAnalysisOverall { level: 'good' | 'attention' | 'caution'; title: string; description: string }
export interface ReportAnalysisSummary { total_items: number; normal_count: number; attention_count: number }
export interface ReportFinding { item_name: string; value: string; status: 'normal' | 'high' | 'low' | 'unknown'; description: string }
export interface ReportAttention { item_name: string; value: string; reference?: string | null; status: 'high' | 'low'; description: string; source_type?: string | null; confidence?: number | null }
export interface ReportSuggestion { title: string; description: string }
export interface ReportAnalysis {
  overall: ReportAnalysisOverall
  summary: ReportAnalysisSummary
  findings: ReportFinding[]
  attention: ReportAttention[]
  suggestions: ReportSuggestion[]
  disclaimer: string
}
export interface ReportAnalysisData {
  analysis_id: string
  report_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  error_message?: string | null
  analysis?: ReportAnalysis | null
  updated_at?: string | null
  meta?: { model?: string | null; profile_available?: boolean } | null
}
export interface ReportAnalysisTrigger { analysis_id: string; status: string; cached: boolean }
export const analyzeHealthCheckReport = (id: string) => request.post<ReportAnalysisTrigger>(`/health-reports/${id}/analyze`).then(r => r.data)
export const getHealthCheckReportAnalysis = (id: string) => request.get<ReportAnalysisData>(`/health-reports/${id}/analysis`).then(r => r.data)
export const reanalyzeHealthCheckReport = (id: string) => request.post<ReportAnalysisTrigger>(`/health-reports/${id}/reanalyze`).then(r => r.data)
