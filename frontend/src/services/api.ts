import axios from 'axios'

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

export function setApiKey(key: string) {
  api.defaults.headers.common['X-API-Key'] = key
}

export function getApiKey(): string | undefined {
  return api.defaults.headers.common['X-API-Key'] as string | undefined
}

export default api

export interface Source {
  id: string
  name: string
  source_type: string
  config: Record<string, unknown>
  category: string | null
  tags: string[]
  enabled: boolean
  refresh_interval_minutes: number
  owner_id: string
  health_status: string
  last_scan_at: string | null
  last_failure_reason: string | null
  suggested_fix: string | null
  created_at: string
  updated_at: string
}

export interface SourceCreate {
  name: string
  source_type: string
  config: Record<string, unknown>
  category?: string
  tags?: string[]
  enabled?: boolean
  refresh_interval_minutes?: number
}

export interface ScanRun {
  id: string
  source_id: string
  status: string
  started_at: string | null
  completed_at: string | null
  items_collected: number
  items_new: number
  items_analyzed: number
  items_failed: number
  error_log: string[]
  suggested_fix: string | null
}

export interface Signal {
  id: string
  source_id: string
  url: string
  title: string | null
  summary: string | null
  published_at: string | null
  collected_at: string
  overall_score: number | null
  signal_strength: number | null
  cross_domain_impact: number | null
  investment_velocity: number | null
  technical_feasibility: number | null
  strategic_fit: number | null
}

export interface Report {
  id: string
  owner_id: string
  title: string | null
  report_type: string
  status: string
  file_path: string | null
  summary_text: string | null
  created_at: string
}

export interface LlmSettings {
  base_url: string
  model: string
  temperature: number
  max_tokens: number
}

export interface ScoringDimension {
  name: string
  weight: number
  enabled: boolean
}

export interface ScoringSettings {
  dimensions: ScoringDimension[]
}

export async function fetchSources(): Promise<Source[]> {
  const res = await api.get('/sources')
  return res.data.sources
}

export async function createSource(payload: SourceCreate): Promise<Source> {
  const res = await api.post('/sources', payload)
  return res.data
}

export async function updateSource(id: string, payload: Partial<SourceCreate>): Promise<Source> {
  const res = await api.put(`/sources/${id}`, payload)
  return res.data
}

export async function deleteSource(id: string): Promise<void> {
  await api.delete(`/sources/${id}`)
}

export async function fetchScannerTypes(): Promise<string[]> {
  const res = await api.get('/sources/scanner-types')
  return res.data.scanner_types
}

export async function fetchScans(): Promise<ScanRun[]> {
  const res = await api.get('/scans')
  return res.data.scans
}

export async function triggerScan(sourceId: string): Promise<ScanRun> {
  const res = await api.post('/scans', { source_id: sourceId })
  return res.data
}

export async function fetchSignals(
  sourceId?: string,
  minScore?: number,
  limit = 100,
  offset = 0
): Promise<{ signals: Signal[]; total: number }> {
  const params: Record<string, unknown> = { limit, offset }
  if (sourceId) params.source_id = sourceId
  if (minScore !== undefined) params.min_score = minScore
  const res = await api.get('/signals', { params })
  return res.data
}

export async function fetchReports(): Promise<Report[]> {
  const res = await api.get('/reports')
  return res.data.reports
}

export async function createReport(payload: {
  title?: string
  item_ids?: string[]
  filters?: Record<string, unknown>
}): Promise<Report> {
  const res = await api.post('/reports', payload)
  return res.data
}

export async function fetchLlmSettings(): Promise<LlmSettings> {
  const res = await api.get('/settings/llm')
  return res.data
}

export async function updateLlmSettings(payload: Partial<LlmSettings>): Promise<LlmSettings> {
  const res = await api.put('/settings/llm', payload)
  return res.data
}

export async function fetchScoringSettings(): Promise<ScoringSettings> {
  const res = await api.get('/settings/scoring')
  return res.data
}

export async function updateScoringSettings(payload: ScoringSettings): Promise<ScoringSettings> {
  const res = await api.put('/settings/scoring', payload)
  return res.data
}
