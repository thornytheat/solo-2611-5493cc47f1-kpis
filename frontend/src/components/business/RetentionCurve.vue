<template>
  <figure class="chart">
    <figcaption class="chart__cap">
      <span class="eyebrow">{{ caption }}</span>
      <span class="chart__legend mono">
        <span class="key key--obs"></span>观察
        <span class="key key--fit"></span>拟合 a·exp(-λm)
      </span>
    </figcaption>
    <svg :viewBox="`0 0 ${width} ${height}`" role="img" class="chart__svg" :aria-label="caption">
      <g class="grid">
        <line v-for="tick in ticks" :key="`g-${tick}`" :x1="pad" :x2="width - pad" :y1="y(tick)" :y2="y(tick)" />
      </g>
      <path v-if="fittedPoints.length" :d="area" class="area" />
      <path v-if="fittedPoints.length" :d="fittedLine" class="fitline" />
      <path v-if="observedPoints.length" :d="observedLine" class="obsline" />
      <g v-for="(point, index) in observedPoints" :key="`p-${point.m}`">
        <circle :cx="x(point.m)" :cy="y(point.rate)" r="3.6" class="dot-obs" :style="{ animationDelay: `${index * 40}ms` }" />
        <circle v-if="point.m === 0 || point.m === 6 || point.m === 12" :cx="x(point.m)" :cy="y(point.rate)" r="7" class="dot-ring" />
      </g>
      <g class="axis">
        <text v-for="point in observedPoints" :key="`t-${point.m}`" :x="x(point.m)" :y="height - 6" text-anchor="middle">
          M{{ point.m }}
        </text>
      </g>
      <g class="axis axis--y">
        <text v-for="tick in ticks" :key="`y-${tick}`" :x="pad - 6" :y="y(tick) + 3" text-anchor="end">
          {{ Math.round(tick * 100) }}%
        </text>
      </g>
    </svg>
  </figure>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { areaPath, buildScales, decayPoints, linePath, type Point } from '../../utils/curve'

const props = withDefaults(
  defineProps<{
    points: Point[]
    caption?: string
    fitted?: { a: number; lam: number; months: number } | null
    width?: number
    height?: number
  }>(),
  { caption: '留存曲线', fitted: null, width: 640, height: 250 },
)

const pad = 34
const ticks = [0, 0.25, 0.5, 0.75, 1]
const scale = computed(() => buildScales(props.points, props.width, props.height, pad))
const x = (m: number) => scale.value.x(m)
const y = (rate: number) => scale.value.y(rate)
const observedPoints = computed(() => props.points)
const fittedPoints = computed<Point[]>(() =>
  props.fitted ? decayPoints(props.fitted.a, props.fitted.lam, props.fitted.months) : [],
)
const observedLine = computed(() => linePath(observedPoints.value, x, y))
const fittedLine = computed(() => linePath(fittedPoints.value, x, y))
const area = computed(() => areaPath(fittedPoints.value, x, y, props.height - pad))
</script>

<style scoped>
.chart { margin: 0; }
.chart__cap { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 6px; flex-wrap: wrap; }
.chart__legend { display: flex; align-items: center; gap: 8px; font-size: 10px; color: var(--coffee-3); }
.key { display: inline-block; width: 14px; height: 2px; }
.key--obs { background: var(--coffee); }
.key--fit { background: repeating-linear-gradient(90deg, var(--coffee-3) 0 3px, transparent 3px 6px); }
.chart__svg { width: 100%; height: auto; display: block; }
.grid line { stroke: var(--rule-soft); stroke-width: 1; stroke-dasharray: 2 4; }
.area { fill: oklch(88% 0.04 78 / 0.5); }
.fitline { fill: none; stroke: var(--coffee-3); stroke-width: 1.6; stroke-dasharray: 4 3; }
.obsline { fill: none; stroke: var(--coffee); stroke-width: 2; }
.dot-obs { fill: var(--coffee); animation: dotIn 420ms var(--ease) both; }
.dot-ring { fill: none; stroke: var(--coffee-2); stroke-width: 1; opacity: 0.5; }
.axis text { font-family: var(--mono); font-size: 9px; fill: var(--coffee-3); }
.axis--y text { font-size: 8.5px; }
@keyframes dotIn {
  from { opacity: 0; transform: scale(0.4); }
  to { opacity: 1; transform: scale(1); }
}
</style>
