<template>
  <figure class="hist">
    <figcaption class="hist__cap">
      <span class="eyebrow">订单金额分布</span>
      <span class="mono hist__meta">{{ totalOrders }} 单 · 客单 ¥{{ avgTicket.toFixed(2) }}</span>
    </figcaption>
    <svg :viewBox="`0 0 ${width} ${height}`" class="hist__svg" role="img" aria-label="订单金额分布">
      <g v-for="(bucket, index) in scaled" :key="bucket.label">
        <rect
          :x="bucket.x"
          :y="bucket.y"
          :width="bucket.w"
          :height="bucket.h"
          :class="`bar bar--${index % 3}`"
          :style="{ animationDelay: `${index * 55}ms` }"
        />
        <text :x="bucket.x + bucket.w / 2" :y="bucket.y - 4" text-anchor="middle" class="hist__value">
          {{ bucket.count }}
        </text>
        <text :x="bucket.x + bucket.w / 2" :y="height - 6" text-anchor="middle" class="hist__label">
          {{ bucket.label }}
        </text>
      </g>
    </svg>
  </figure>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    buckets: { label: string; count: number }[]
    totalOrders?: number
    avgTicket?: number
    width?: number
    height?: number
  }>(),
  { totalOrders: 0, avgTicket: 0, width: 560, height: 200 },
)

const scaled = computed(() => {
  const max = Math.max(1, ...props.buckets.map((b) => b.count))
  const gap = 12
  const pad = 18
  const barW = (props.width - pad * 2 - gap * (props.buckets.length - 1)) / props.buckets.length
  const usable = props.height - 46
  return props.buckets.map((bucket, index) => {
    const h = Math.max(4, (bucket.count / max) * usable)
    return {
      ...bucket,
      x: pad + index * (barW + gap),
      w: barW,
      h,
      y: props.height - 26 - h,
    }
  })
})
</script>

<style scoped>
.hist { margin: 0; }
.hist__cap { display: flex; align-items: center; justify-content: space-between; gap: 10px; margin-bottom: 4px; flex-wrap: wrap; }
.hist__meta { font-size: 10px; color: var(--coffee-3); }
.hist__svg { width: 100%; height: auto; display: block; }
.bar { animation: barIn 460ms var(--ease) both; }
.bar--0 { fill: var(--roast-3); }
.bar--1 { fill: var(--roast-4); }
.bar--2 { fill: var(--roast-5); }
.hist__value { font-family: var(--mono); font-size: 9px; fill: var(--coffee-2); }
.hist__label { font-family: var(--mono); font-size: 8.5px; fill: var(--coffee-3); }
@keyframes barIn {
  from { opacity: 0; transform: scaleY(0.2); transform-origin: bottom; }
  to { opacity: 1; transform: scaleY(1); transform-origin: bottom; }
}
</style>
