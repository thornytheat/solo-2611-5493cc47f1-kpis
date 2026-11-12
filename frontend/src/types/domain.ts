export interface RetentionCell {
  m: number
  active: number
  rate: number | null
  rate_label: string
  state: 'observed' | 'right_censored'
  revenue: number
}

export interface MatrixRow {
  month: string
  size: number
  observed_months: number
  low_sample: boolean
  cells: RetentionCell[]
}

export interface MatrixColumn {
  m: number
  active: number
  base: number
  rate: number | null
  rate_label: string
}

export interface MatrixStats {
  cohorts: number
  cells_total: number
  cells_observed: number
  cells_censored: number
  low_sample_cells: number
  orders: number
  members: number
  revenue_total: number
  cumulative_arpu: number
}

export interface MatrixPayload {
  snapshot_month: string
  months: number
  cohorts: MatrixRow[]
  columns: MatrixColumn[]
  stats: MatrixStats
  notes: Record<string, string>
}

export interface CurvePoint {
  m: number
  active: number
  rate: number
  rate_label: string
  revenue: number
}

export interface ChannelMixEntry {
  members: number
  cac: number
}

export interface CohortDetail {
  month: string
  size: number
  observed_months: number
  snapshot_month: string
  low_sample: boolean
  note: string
  curve: CurvePoint[]
  amount_distribution: {
    buckets: { label: string; count: number }[]
    orders: number
    total: number
    avg_ticket: number
  }
  channels: {
    channel: string
    label: string
    short: string
    note: string
    members: number
    sample_size: number
    low_sample: boolean
    revenue: number
    revenue_per_member: number
    m1: number | null
    m3: number | null
    m6: number | null
  }[]
  summary: {
    cumulative_revenue: number
    arpu: number
    m1: number | null
    m6: number | null
    m12: number | null
  }
}

export interface CohortSummary {
  month: string
  size: number
  observed_months: number
  cumulative_revenue: number
  arpu: number
  avg_active_ratio: number
  low_sample: boolean
  channel_mix: Record<string, ChannelMixEntry>
}

export interface FitCurvePoint {
  m: number
  observed: number
  fitted: number
  weight: number
}

export interface FitInfo {
  model: string
  lambda: number
  lambda_exact: number
  a: number
  a_exact: number
  r2: number
  r2_exact: number
  cells_used: number
  cells_censored: number
  decay_factor_12m: number
  curve: FitCurvePoint[]
}

export interface ChannelRow {
  channel: string
  label: string
  short: string
  note: string
  cac: number
  members: number
  observed_months: number
  cum_per_member: number
  monthly_revenue: number
  monthly_margin: number
  payback_months: number
  payback_exact: number
  arpu0: number
  ltv_hist: number
  ltv_pred12: number
  rank: number
  low_sample: boolean
}

export interface LtvResults {
  snapshot_month: string
  params: Record<string, any>
  fit: FitInfo
  arpu0: number
  ltv_hist: number
  ltv_hist_exact: number
  ltv_pred12: number
  ltv_pred12_exact: number
  lift_ratio: number
  totals: {
    cohorts: number
    members: number
    observed_cells: number
    censored_cells: number
    revenue: number
  }
  channels: ChannelRow[]
  low_sample: {
    cohorts: { month: string; size: number }[]
    channel_cells: { month: string; channel: string; members: number }[]
  }
  notes: Record<string, string>
}

export interface LtvReport {
  id: string
  name: string
  status: string
  created_at: string
  published_at: string | null
  params: Record<string, any>
  results: LtvResults
}

export interface LtvReportSummary {
  id: string
  name: string
  status: string
  created_at: string
  published_at: string | null
  ltv_hist: number | null
  ltv_pred12: number | null
  lam: number | null
  r2: number | null
}

export interface SensitivityPayload {
  lambda_base: number
  lambda_variants: number[]
  delta_lambda: number
  rows: { channel: string; short: string; cac: number; cells: { lambda: number; ltv_pred12: number }[] }[]
  cac_scales: number[]
  cac_rows: { channel: string; short: string; cells: { scale: number; cac: number; payback_months: number }[] }[]
  forecast_months: number
  arpu0: number
}

export interface ChannelComparison {
  source: 'published' | 'live'
  report_id: string | null
  report_name: string
  published_at: string | null
  snapshot_month: string
  fit: FitInfo
  ltv_hist: number
  ltv_pred12: number
  arpu0: number
  margin_rate: number
  rows: ChannelRow[]
  totals: {
    channels: number
    members: number
    best_payback: number | null
    worst_payback: number | null
    weighted_cac: number
  }
  scope: { channel_scope: string | null; scoped: boolean }
  low_sample: {
    cohorts: { month: string; size: number }[]
    channel_cells: { month: string; channel: string; members: number }[]
  }
  notes: Record<string, string>
}
