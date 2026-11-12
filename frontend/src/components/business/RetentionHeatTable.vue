<template>
  <div class="heat">
    <div class="heat__head">
      <div class="heat__brand">
        <div class="eyebrow">同期群 × 月序</div>
        <div class="heat__title serif">留存矩阵</div>
      </div>
      <div class="heat__meta mono">
        <span>{{ payload.stats.cohorts }} 群</span>
        <span class="dot"></span>
        <span>{{ payload.months }} 月列</span>
        <span class="dot"></span>
        <span>右删失 {{ payload.stats.cells_censored }} 格</span>
      </div>
    </div>

    <div class="scroll-x">
      <table class="matrix">
        <thead>
          <tr>
            <th class="matrix__corner">首单月 / 规模</th>
            <th v-for="col in payload.columns" :key="col.m" class="matrix__mh">
              <span class="matrix__m">M{{ col.m }}</span>
            </th>
            <th class="matrix__mh matrix__mh--sum">观察</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, index) in payload.cohorts"
            :key="row.month"
            :class="['matrix__row', { 'is-highlight': row.month === highlight }]"
            :style="{ animationDelay: `${Math.min(index * 26, 320)}ms` }"
            class="rise"
            @click="$emit('select', row.month)"
          >
            <th class="matrix__label">
              <span class="matrix__month mono">{{ row.month }}</span>
              <span class="matrix__size mono">{{ row.size }}</span>
              <span v-if="row.low_sample" class="tag tag--warn">低样本</span>
            </th>
            <td v-for="cell in row.cells" :key="cell.m" class="matrix__cell-wrap">
              <div
                v-if="cell.state === 'right_censored'"
                class="cell cell--censor"
                :title="`${row.month} M${cell.m}：右删失（快照月尚未走到）`"
              >
                <span class="cell__value">—</span>
                <span class="cell__hint">删失</span>
              </div>
              <div
                v-else
                class="cell"
                :class="`roast-${roastLevel(cell.rate)}`"
                :title="`${row.month} M${cell.m}：${cell.active} / ${row.size} 人，营收 ¥${cell.revenue.toLocaleString('zh-CN')}`"
              >
                <span class="cell__value">{{ compact(cell.rate) }}</span>
              </div>
            </td>
            <td class="matrix__obs mono">{{ row.observed_months }}</td>
          </tr>
        </tbody>
        <tfoot>
          <tr>
            <th class="matrix__label matrix__label--foot">列合计留存</th>
            <td v-for="col in payload.columns" :key="`f-${col.m}`" class="matrix__cell-wrap">
              <div class="cell cell--column">
                <span class="cell__value">{{ col.rate_label }}</span>
              </div>
            </td>
            <td class="matrix__obs mono">
              {{ payload.stats.cells_observed }}/{{ payload.stats.cells_total }}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>

    <div class="heat__foot">
      <RoastLegend top-label="55%+" />
      <p class="heat__note">{{ payload.notes.censor }}</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { MatrixPayload } from '../../types/domain'
import { roastLevel } from '../../utils/format'
import RoastLegend from '../common/RoastLegend.vue'

defineProps<{ payload: MatrixPayload; highlight?: string | null }>()
defineEmits<{ select: [month: string] }>()

function compact(rate: number | null): string {
  if (rate === null || rate === undefined) return '—'
  const pct = rate * 100
  // 保留一位小数，只有 100% 取整（格子宽度按 4 字符设计）
  return pct >= 99.95 ? '100' : pct.toFixed(1)
}
</script>

<style scoped>
.heat { border: var(--hair); background: var(--cream-2); }
.heat__head {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 16px;
  padding: 10px 18px 8px;
  border-bottom: var(--hair);
}
.heat__title { font-size: 17px; margin-top: 2px; }
.heat__meta { display: flex; align-items: center; gap: 8px; font-size: 10.5px; color: var(--coffee-3); }
.dot { width: 3px; height: 3px; border-radius: 50%; background: var(--coffee-3); }

.matrix { width: 100%; border-collapse: collapse; min-width: 800px; table-layout: auto; }
.matrix th, .matrix td { padding: 3px 2px; }
.matrix__corner {
  font-family: var(--mono); font-size: 10px; letter-spacing: 0.1em; color: var(--coffee-3);
  text-align: left; padding: 8px 10px; font-weight: 500; white-space: nowrap;
}
.matrix__mh { font-family: var(--mono); font-size: 10px; color: var(--coffee-3); font-weight: 500; }
.matrix__mh--sum, .matrix__obs { width: 58px; }
.matrix__m { display: block; padding-bottom: 2px; }
.matrix__row { cursor: pointer; transition: background-color 200ms var(--ease); }
.matrix__row:hover { background: var(--cream-3); }
.matrix__row.is-highlight { background: var(--cream-3); box-shadow: inset 3px 0 0 var(--coffee); }
.matrix__label {
  text-align: left; padding: 3px 10px; white-space: nowrap;
  display: table-cell;
}
.matrix__month { font-size: 11.5px; color: var(--espresso); margin-right: 7px; }
.matrix__size { font-size: 9.5px; color: var(--coffee-3); margin-right: 6px; }
.matrix__label .tag { font-size: 8.5px; padding: 1px 4px; }
.matrix__label--foot { font-size: 10px; color: var(--coffee-3); font-family: var(--mono); font-weight: 500; }
.matrix__obs { font-family: var(--mono); font-size: 10.5px; color: var(--coffee-3); text-align: center; }

.cell {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  height: 29px; min-width: 42px;
  border: 1px solid transparent;
  transition: transform 220ms var(--ease), outline-color 220ms var(--ease);
}
.cell:hover { transform: translateY(-1px); outline: 1px solid var(--coffee); }
.cell__value { font-family: var(--mono); font-size: 11px; font-variant-numeric: tabular-nums; }
.cell__hint { font-family: var(--mono); font-size: 8px; letter-spacing: 0.08em; opacity: 0.75; }
.cell--censor {
  background-image: repeating-linear-gradient(45deg, var(--cream-4) 0 3px, var(--cream-2) 3px 6px);
  color: var(--coffee-3);
  border: 1px dashed var(--rule);
}
.cell--column { background: transparent; border-top: 1px solid var(--rule-soft); }
.cell--column .cell__value { font-size: 10px; color: var(--coffee-2); }

.roast-0 { background: var(--roast-0); color: var(--espresso); }
.roast-1 { background: var(--roast-1); color: var(--espresso); }
.roast-2 { background: var(--roast-2); color: var(--espresso); }
.roast-3 { background: var(--roast-3); color: var(--cream-2); }
.roast-4 { background: var(--roast-4); color: var(--cream-2); }
.roast-5 { background: var(--roast-5); color: var(--cream-2); }
.roast-6 { background: var(--roast-6); color: var(--cream-2); }
.roast--1 { background: transparent; }

.heat__foot {
  display: flex; align-items: center; gap: 22px; flex-wrap: wrap;
  padding: 10px 18px 12px; border-top: var(--hair);
}
.heat__note { margin: 0; font-size: 11px; color: var(--coffee-3); max-width: 62ch; }
</style>
