/** 错误码 → 默认文案（后端优先，网络异常时兜底）。 */
export const ERROR_MESSAGES: Record<string, string> = {
  AUTH_REQUIRED: '请先登录',
  AUTH_INVALID: '登录状态无效，请重新登录',
  TOKEN_EXPIRED: '登录已过期，请重新登录',
  FORBIDDEN: '当前角色无权执行该操作',
  NOT_FOUND: '对象不存在',
  VALIDATION_ERROR: '请求参数不合法',
  MATRIX_EMPTY: '留存矩阵还没有数据，请先重建矩阵',
  MATRIX_STALE: '矩阵口径已变化，请重建后再测算',
  REPORT_NOT_FOUND: '测算报告不存在',
  REPORT_NOT_PUBLISHED: '该报告尚未发布，渠道视图不可见',
  REPORT_ALREADY_PUBLISHED: '该报告已发布，不能重复发布',
  FIT_FAILED: '衰减曲线拟合失败，请检查观察期参数',
  NO_OBSERVED_CELLS: '观察期不足，没有可用于拟合的有效格子',
  LOW_SAMPLE_ONLY: '样本量不足（<30），不参与渠道排行',
  JOB_NOT_FOUND: '任务不存在或已过期',
  RATE_LIMITED: '请求过于频繁，请稍后重试',
  INTERNAL_ERROR: '服务内部错误',
}

export const EMPTY_HINTS = {
  matrix: '矩阵为空通常是订单事实还没入库。到「留存矩阵」点「重建矩阵」，或检查 seed 是否跑过。',
  cohort: '这个群在快照月之前没有订单记录，换一个月份试试。',
  ltv: '先跑一次测算：确认观察期与渠道 CAC 后点「运行测算」。',
  channels: '渠道对比来自最新已发布的测算报告，先去「LTV 测算」发布一份。',
  audit: '暂无审计记录，登录或重建矩阵后会写入。',
}
