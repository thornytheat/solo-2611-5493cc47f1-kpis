/** 展示层格式化。数值本身全部来自后端，这里只做单位与小数位。 */

export function money(value: number | null | undefined, digits = 0): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `¥${value.toLocaleString('zh-CN', {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })}`
}

export function percent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return `${(value * 100).toFixed(digits)}%`
}

export function fixed(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return value.toFixed(digits)
}

export function integer(value: number | null | undefined): string {
  if (value === null || value === undefined || Number.isNaN(value)) return '—'
  return Math.round(value).toLocaleString('zh-CN')
}

export function monthLabel(month: string): string {
  return month.replace('-', '.')
}

export function monthShort(month: string): string {
  const [, mon] = month.split('-')
  return mon
}

export function relativeDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  const date = new Date(iso)
  if (Number.isNaN(date.getTime())) return '—'
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 烘豆色阶：留存率 → 0..6 档（与 tokens.css --roast-* 对应） */
export function roastLevel(rate: number | null | undefined): number {
  if (rate === null || rate === undefined) return -1
  const thresholds = [0.06, 0.12, 0.18, 0.26, 0.38, 0.55]
  for (let i = 0; i < thresholds.length; i += 1) {
    if (rate < thresholds[i]) return i
  }
  return 6
}
