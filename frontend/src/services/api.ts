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

export interface SharePointConnection {
  id: string
  name: string
  site_id: string | null
  site_url: string | null
  list_id: string | null
  drive_id: string | null
  tenant_id: string
  client_id: string
  is_enabled: boolean
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface SharePointConnectionCreate {
  name: string
  site_id?: string
  site_url?: string
  list_id?: string
  drive_id?: string
  tenant_id: string
  client_id: string
  client_secret: string
  is_enabled?: boolean
  is_default?: boolean
}

export async function fetchSharePointConnections(): Promise<SharePointConnection[]> {
  const res = await api.get('/sharepoint/connections')
  return res.data
}

export async function createSharePointConnection(payload: SharePointConnectionCreate): Promise<SharePointConnection> {
  const res = await api.post('/sharepoint/connections', payload)
  return res.data
}

export async function updateSharePointConnection(id: string, payload: Partial<SharePointConnectionCreate>): Promise<SharePointConnection> {
  const res = await api.patch(`/sharepoint/connections/${id}`, payload)
  return res.data
}

export async function deleteSharePointConnection(id: string): Promise<void> {
  await api.delete(`/sharepoint/connections/${id}`)
}

export async function checkSharePointHealth(id: string): Promise<{ status: string; message?: string }> {
  const res = await api.get(`/sharepoint/connections/${id}/health`)
  return res.data
}

export async function uploadReportToSharePoint(reportId: string, connectionId: string): Promise<SharePointConnection> {
  const res = await api.post('/sharepoint/upload', { report_id: reportId, connection_id: connectionId })
  return res.data
}

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
  review_status?: string
  human_score?: number | null
  assigned_reviewer_id?: string | null
  metadata_json?: Record<string, unknown>
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

export interface TrendPoint {
  id: string
  workspace_id: string | null
  category: string
  topic_key: string
  date_bucket: string
  granularity: 'day' | 'week' | 'month'
  item_count: number
  avg_overall_score: number | null
  avg_signal_strength: number | null
  avg_cross_domain_impact: number | null
  avg_investment_velocity: number | null
  avg_technical_feasibility: number | null
  avg_strategic_fit: number | null
  summary: string | null
  source_ids: string[]
  created_at: string
  updated_at: string
}

export interface TrendSeries {
  category: string | null
  topic_key: string | null
  granularity: 'day' | 'week' | 'month'
  points: TrendPoint[]
}

export interface TrendComparison {
  series: TrendSeries[]
}

export interface TrendEvidence {
  id: string
  trend_point_id: string
  raw_item_id: string
  source_id: string
  rank: number
  overall_score: number | null
  dimension_scores: Record<string, number | null>
  rationale: string | null
  raw_item_title: string | null
  raw_item_url: string | null
  source_name: string | null
}

export interface TrendAggregateRequest {
  category?: string
  topic_key?: string
  start_date?: string
  end_date?: string
  granularity?: 'day' | 'week' | 'month'
  top_evidence_count?: number
  only_approved?: boolean
}

export async function aggregateTrends(payload: TrendAggregateRequest): Promise<TrendPoint[]> {
  const res = await api.post('/trends/aggregate', payload)
  return res.data
}

export async function fetchTrendSeries(
  category?: string,
  topic?: string,
  startDate?: string,
  endDate?: string,
  granularity: 'day' | 'week' | 'month' = 'week',
  compareTopics?: string[]
): Promise<TrendComparison> {
  const params: Record<string, unknown> = { granularity }
  if (category) params.category = category
  if (topic) params.topic_key = topic
  if (startDate) params.start_date = startDate
  if (endDate) params.end_date = endDate
  if (compareTopics?.length) params.compare_topics = compareTopics
  const res = await api.get('/trends/series', { params })
  return res.data
}

export async function fetchTrendEvidence(trendPointId: string): Promise<TrendEvidence[]> {
  const res = await api.get(`/trends/points/${trendPointId}/evidence`)
  return res.data
}

export async function fetchTrendCategories(): Promise<string[]> {
  const res = await api.get('/trends/categories')
  return res.data.categories
}

export async function fetchTrendTopics(category?: string): Promise<string[]> {
  const res = await api.get('/trends/topics', { params: category ? { category } : {} })
  return res.data.topics
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
  offset = 0,
  reviewStatus?: string
): Promise<{ signals: Signal[]; total: number }> {
  const params: Record<string, unknown> = { limit, offset }
  if (sourceId) params.source_id = sourceId
  if (minScore !== undefined) params.min_score = minScore
  if (reviewStatus) params.review_status = reviewStatus
  const res = await api.get('/signals', { params })
  return res.data
}

export type ReviewAction = 'approve' | 'reject' | 'flag' | 'override'
export type BulkReviewAction = 'approve' | 'reject' | 'flag'
export type FeedbackType = 'score_too_low' | 'score_too_high' | 'irrelevant'

export interface ReviewActionRequest {
  action: ReviewAction
  human_score?: number
  notes?: string
}

export interface BulkReviewRequest {
  item_ids: string[]
  action: BulkReviewAction
  notes?: string
}

export interface BulkReviewFailure {
  id: string
  error: string
}

export interface BulkReviewResult {
  succeeded: string[]
  failed: BulkReviewFailure[]
}

export interface FeedbackRequest {
  human_score: number
  feedback_type: FeedbackType
  notes?: string
}

export interface ReviewRecord {
  id: string
  raw_item_id: string
  workspace_id: string
  reviewer_id: string | null
  status: string
  human_score: number | null
  notes: string | null
  created_at: string | null
}

export interface ReviewQueueParams {
  source_id?: string
  category?: string
  assigned_to_me?: boolean
  limit?: number
  offset?: number
}

export async function fetchReviewQueue(
  params: ReviewQueueParams = {}
): Promise<{ signals: Signal[]; total: number }> {
  const res = await api.get('/signals/review-queue', { params })
  return res.data
}

export async function reviewSignal(id: string, payload: ReviewActionRequest): Promise<ReviewRecord> {
  const res = await api.post(`/signals/${id}/review`, payload)
  return res.data
}

export async function bulkReviewSignals(payload: BulkReviewRequest): Promise<BulkReviewResult> {
  const res = await api.post('/signals/bulk-review', payload)
  return res.data
}

export async function submitSignalFeedback(id: string, payload: FeedbackRequest): Promise<ReviewRecord> {
  const res = await api.post(`/signals/${id}/feedback`, payload)
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
  report_type?: 'pdf' | 'pptx' | 'card'
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

// ---------------------------------------------------------------------------
// Scan schedules
// ---------------------------------------------------------------------------

export interface ScanSchedule {
  id: string
  source_id: string
  cron_expression: string
  timezone: string
  is_enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  created_at: string
  updated_at: string
}

export interface ScanScheduleRequest {
  source_id: string
  cron_expression?: string
  timezone?: string
  is_enabled?: boolean
}

export async function fetchSchedules(): Promise<ScanSchedule[]> {
  const res = await api.get('/schedules')
  return res.data
}

export async function createSchedule(payload: ScanScheduleRequest): Promise<ScanSchedule> {
  const res = await api.post('/schedules', payload)
  return res.data
}

export async function deleteSchedule(id: string): Promise<void> {
  await api.delete(`/schedules/${id}`)
}

// ---------------------------------------------------------------------------
// Notification channels
// ---------------------------------------------------------------------------

export interface NotificationChannel {
  id: string
  owner_id: string
  channel_type: string
  name: string
  is_enabled: boolean
  on_scan_success: boolean
  on_scan_failure: boolean
  created_at: string
  updated_at: string
}

export interface NotificationChannelRequest {
  channel_type: 'email' | 'teams_webhook'
  name: string
  config: Record<string, unknown>
  on_scan_success?: boolean
  on_scan_failure?: boolean
}

export async function fetchNotificationChannels(): Promise<NotificationChannel[]> {
  const res = await api.get('/notifications/channels')
  return res.data
}

export async function createNotificationChannel(payload: NotificationChannelRequest): Promise<NotificationChannel> {
  const res = await api.post('/notifications/channels', payload)
  return res.data
}

export async function deleteNotificationChannel(id: string): Promise<void> {
  await api.delete(`/notifications/channels/${id}`)
}

// ---------------------------------------------------------------------------
// Semantic search
// ---------------------------------------------------------------------------

export interface SimilarSignal {
  signal: Signal
  similarity: number
}

export interface SemanticSearchResult {
  query: string
  results: SimilarSignal[]
}

export async function semanticSearchSignals(query: string, limit = 20): Promise<SemanticSearchResult> {
  const res = await api.get('/signals/semantic-search', { params: { q: query, limit } })
  return res.data
}

// ---------------------------------------------------------------------------
// Embed tokens (SharePoint)
// ---------------------------------------------------------------------------

export interface EmbedToken {
  id: string
  workspace_id: string
  name: string
  token_prefix: string
  scopes: string
  expires_at: string
  revoked_at: string | null
  last_used_at: string | null
  created_at: string
  updated_at: string
}

export interface EmbedTokenWithPlaintext {
  token: string
  embed_token: EmbedToken
}

export async function fetchEmbedTokens(workspaceId: string): Promise<EmbedToken[]> {
  const res = await api.get(`/workspaces/${workspaceId}/embed-tokens`)
  return res.data
}

export async function createEmbedToken(
  workspaceId: string,
  payload: { name?: string; ttl_days?: number }
): Promise<EmbedTokenWithPlaintext> {
  const res = await api.post(`/workspaces/${workspaceId}/embed-token`, payload)
  return res.data
}

export async function revokeEmbedToken(workspaceId: string, tokenId: string): Promise<EmbedToken> {
  const res = await api.post(`/workspaces/${workspaceId}/embed-tokens/${tokenId}/revoke`, {})
  return res.data
}

export async function rotateEmbedToken(
  workspaceId: string,
  tokenId: string,
  payload: { name?: string; ttl_days?: number } = {}
): Promise<EmbedTokenWithPlaintext> {
  const res = await api.post(`/workspaces/${workspaceId}/embed-tokens/${tokenId}/rotate`, payload)
  return res.data
}

// ---------------------------------------------------------------------------
// Review assignments
// ---------------------------------------------------------------------------

export interface ReviewAssignment {
  id: string
  workspace_id: string
  category: string
  reviewer_id: string
  created_at: string
}

export interface ReviewAssignmentRequest {
  category: string
  reviewer_id: string
}

export async function fetchReviewAssignments(): Promise<ReviewAssignment[]> {
  const res = await api.get('/review-assignments')
  return res.data
}

export async function createReviewAssignment(payload: ReviewAssignmentRequest): Promise<ReviewAssignment> {
  const res = await api.post('/review-assignments', payload)
  return res.data
}

export async function deleteReviewAssignment(id: string): Promise<void> {
  await api.delete(`/review-assignments/${id}`)
}
