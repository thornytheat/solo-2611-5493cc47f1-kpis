export interface ApiError {
  code: string
  message: string
  detail?: string
  traceId?: string | null
  status?: number
}

export interface JobStatusPayload {
  job_id: string
  status: string
  submitted_at?: string
  started_at?: string
  finished_at?: string
  elapsed_ms?: number
  summary?: {
    cells: number
    cells_observed: number
    cells_censored: number
    low_sample_cells: number
    cohorts: number
    months: number
    snapshot_month: string
  } | null
  detail?: string | null
}
