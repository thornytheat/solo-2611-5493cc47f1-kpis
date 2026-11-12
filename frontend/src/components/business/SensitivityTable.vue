<template>
  <div class="sense">
    <div class="spread">
      <div>
        <div class="eyebrow">敏感性 · λ 与 CAC</div>
        <div class="sense__title serif">参数扰动下的回本与 LTV</div>
      </div>
      <span class="tag">λ 基准 {{ payload.lambda_base.toFixed(3) }}</span>
    </div>

    <table class="table">
      <thead>
        <tr>
          <th>渠道</th>
          <th class="num" v-for="value in payload.lambda_variants" :key="`l-${value}`">
            λ={{ value.toFixed(3) }}<br /><span class="th-sub">预测 12 月 LTV</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in payload.rows" :key="row.channel">
          <td>{{ row.short }}</td>
          <td v-for="cell in row.cells" :key="`c-${row.channel}-${cell.lambda}`" class="num">
            {{ money(cell.ltv_pred12) }}
          </td>
        </tr>
      </tbody>
    </table>

    <table class="table">
      <thead>
        <tr>
          <th>渠道</th>
          <th class="num" v-for="scale in payload.cac_scales" :key="`s-${scale}`">
            CAC ×{{ scale }}<br /><span class="th-sub">回本周期（月）</span>
          </th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in payload.cac_rows" :key="`cac-${row.channel}`">
          <td>{{ row.short }}</td>
          <td v-for="cell in row.cells" :key="`cell-${row.channel}-${cell.scale}`" class="num">
            <span :class="{ warn: cell.payback_months > 6 }">{{ cell.payback_months.toFixed(1) }}</span>
          </td>
        </tr>
      </tbody>
    </table>
    <p class="sense__note">{{ payload.forecast_months }} 月预测窗 · ARPU₀ {{ money(payload.arpu0) }}</p>
  </div>
</template>

<script setup lang="ts">
import type { SensitivityPayload } from '../../types/domain'
import { money } from '../../utils/format'

defineProps<{ payload: SensitivityPayload }>()
</script>

<style scoped>
.sense { display: flex; flex-direction: column; gap: 12px; }
.sense__title { font-size: 15px; margin-top: 2px; }
.th-sub { font-size: 9px; letter-spacing: 0.04em; color: var(--coffee-4); text-transform: none; }
.sense__note { margin: 0; font-size: 10.5px; color: var(--coffee-3); font-family: var(--mono); }
.warn { color: var(--brick); }
</style>
