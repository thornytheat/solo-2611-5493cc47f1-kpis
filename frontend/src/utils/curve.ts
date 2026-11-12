/** SVG 曲线工具：把 (m, rate) 点列变成路径。图表全部自绘，不引第三方库。 */

export interface Point {
  m: number
  rate: number
}

export function buildScales(points: Point[], width: number, height: number, pad: number) {
  const maxM = points.length ? points[points.length - 1].m : 1
  const innerW = width - pad * 2
  const innerH = height - pad * 2
  const x = (m: number) => pad + (maxM === 0 ? innerW / 2 : (m / maxM) * innerW)
  const y = (rate: number) => pad + innerH - Math.min(1, Math.max(0, rate)) * innerH
  return { x, y, innerW, innerH, pad, maxM }
}

export function linePath(points: Point[], x: (m: number) => number, y: (rate: number) => number): string {
  if (!points.length) return ''
  return points
    .map((point, index) => `${index === 0 ? 'M' : 'L'}${x(point.m).toFixed(2)},${y(point.rate).toFixed(2)}`)
    .join(' ')
}

export function areaPath(
  points: Point[],
  x: (m: number) => number,
  y: (rate: number) => number,
  baseline: number,
): string {
  if (!points.length) return ''
  const head = `M${x(points[0].m).toFixed(2)},${baseline.toFixed(2)}`
  const body = points
    .map((point) => `L${x(point.m).toFixed(2)},${y(point.rate).toFixed(2)}`)
    .join(' ')
  const tail = `L${x(points[points.length - 1].m).toFixed(2)},${baseline.toFixed(2)} Z`
  return `${head} ${body} ${tail}`
}

/** 拟合曲线：y = a·exp(-λ·m)，m 取 0..months-1 */
export function decayPoints(a: number, lam: number, months: number): Point[] {
  return Array.from({ length: months }, (_, m) => ({ m, rate: a * Math.exp(-lam * m) }))
}
