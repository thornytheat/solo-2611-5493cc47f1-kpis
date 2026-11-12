/** 共享枚举（前端）：渠道 / 留存格状态 / 报告状态 / 任务状态 / 衰减模型。
 *  与后端 src/constants/enums.py 一一对应，README「枚举出现位置」列出全部落点。 */
export const Channel = {
  Private: 'private',
  PaidFeed: 'paid_feed',
  Store: 'store',
  Partner: 'partner',
  All: 'all',
} as const
export type ChannelCode = (typeof Channel)[keyof typeof Channel]

export const CHANNEL_CODES: ChannelCode[] = [
  Channel.Private,
  Channel.PaidFeed,
  Channel.Store,
  Channel.Partner,
]

export const CHANNEL_LABELS: Record<ChannelCode, string> = {
  private: '私域社群',
  paid_feed: '信息流投放',
  store: '门店自然流',
  partner: '异业合作',
  all: '全渠道',
}

export const CHANNEL_SHORT: Record<ChannelCode, string> = {
  private: '私域',
  paid_feed: '信息流',
  store: '门店',
  partner: '异业',
  all: '汇总',
}

export const CellState = {
  Observed: 'observed',
  RightCensored: 'right_censored',
} as const
export type CellStateCode = (typeof CellState)[keyof typeof CellState]

export const ReportStatus = {
  Draft: 'draft',
  Published: 'published',
  Archived: 'archived',
  Superseded: 'superseded',
} as const
export type ReportStatusCode = (typeof ReportStatus)[keyof typeof ReportStatus]

export const REPORT_STATUS_LABELS: Record<string, string> = {
  draft: '待复核',
  published: '已发布',
  archived: '已归档',
  superseded: '已被替代',
}

/** 复核状态：发布进度 × 数据新旧（与后端 ReviewState 一一对应）。 */
export const ReviewState = {
  Draft: 'draft',
  Published: 'published',
  Superseded: 'superseded',
  StaleDraft: 'stale_draft',
  StalePublished: 'stale_published',
} as const
export type ReviewStateCode = (typeof ReviewState)[keyof typeof ReviewState]

export const REVIEW_STATE_LABELS: Record<string, string> = {
  draft: '待复核',
  published: '已发布 · 口径冻结',
  superseded: '已被新版本替代',
  stale_draft: '数据已更新 · 待重算',
  stale_published: '已发布但数据过期 · 待新版本接管',
  live: '现场测算（未发布）',
}

export const ImportBatchStatus = {
  Validated: 'validated',
  Applied: 'applied',
  Failed: 'failed',
  Rejected: 'rejected',
} as const
export type ImportBatchStatusCode = (typeof ImportBatchStatus)[keyof typeof ImportBatchStatus]

export const IMPORT_BATCH_STATUS_LABELS: Record<string, string> = {
  validated: '校验通过（未落库）',
  applied: '已切换',
  failed: '校验失败（未改动）',
  rejected: '拒绝（重复/晚到）',
}

export const JobStatus = {
  Queued: 'queued',
  Running: 'running',
  Succeeded: 'succeeded',
  Failed: 'failed',
} as const
export type JobStatusCode = (typeof JobStatus)[keyof typeof JobStatus]

export const JOB_STATUS_LABELS: Record<string, string> = {
  queued: '排队中',
  running: '重建中',
  succeeded: '已完成',
  failed: '失败',
}

export const DecayModel = {
  Exponential: 'exponential',
} as const
export type DecayModelCode = (typeof DecayModel)[keyof typeof DecayModel]

export const DECAY_MODEL_LABELS: Record<string, string> = {
  exponential: '指数衰减 R_m = a·exp(-λm)',
}
