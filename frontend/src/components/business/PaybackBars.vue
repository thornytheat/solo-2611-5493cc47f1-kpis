<template>
  <div class="bars">
    <div v-for="row in rows" :key="row.channel" class="bars__row">
      <div class="bars__label">
        <span class="bars__name">{{ row.short }}</span>
        <span class="bars__cac mono">CAC {{ money(row.cac) }}</span>
      </div>
      <div class="bars__track">
        <div
          class="bars__fill"
          :class="{ 'is-slow': row.payback_months > 3, 'is-fast': row.payback_months <= 1.5 }"
          :style="{ width: `${width(row.payback_months)}%` }"
        ></div>
        <span class="bars__value mono">{{ row.payback_months.toFixed(1) }} 月</span>
      </div>
    </div>
    <div class="bars__scale mono">
      <span>0</span><span>2</span><span>4</span><span>6+ 月</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ChannelRow } from '../../types/domain'
import { money } from '../../utils/format'

const props = defineProps<{ rows: ChannelRow[] }>()
const max = 6
function width(value: number): number {
  return Math.min(100, (value / max) * 100)
}
void props
</script>

<style scoped>
.bars { display: flex; flex-direction: column; gap: 9px; }
.bars__row { display: grid; grid-template-columns: 108px minmax(0, 1fr); align-items: center; gap: 10px; }
.bars__label { display: flex; flex-direction: column; line-height: 1.25; }
.bars__name { font-size: 12.5px; }
.bars__cac { font-size: 9.5px; color: var(--coffee-3); }
.bars__track { display: flex; align-items: center; gap: 8px; }
.bars__fill {
  height: 11px; min-width: 6px;
  background: var(--coffee-3);
  transition: width 620ms var(--ease);
}
.bars__fill.is-slow { background: var(--brick); }
.bars__fill.is-fast { background: var(--sage); }
.bars__value { font-size: 10.5px; color: var(--coffee-2); white-space: nowrap; }
.bars__scale {
  display: flex; justify-content: space-between;
  font-size: 9px; color: var(--coffee-4);
  padding-left: 118px; border-top: 1px dashed var(--rule-soft); padding-top: 4px;
}
@media (max-width: 767px) {
  .bars__row { grid-template-columns: 84px minmax(0, 1fr); }
  .bars__scale { padding-left: 94px; }
}
</style>
