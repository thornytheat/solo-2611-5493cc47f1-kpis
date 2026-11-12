export interface ApiError {
  code: string
  message: string
  detail?: string
  traceId?: string | null
  status?: number
  extra?: {
    batch_id?: string
    errors?: Array<{ index: number; order_no: string; field: string; message: string }>
    retry_after?: number
    [key: string]: unknown
  }
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
