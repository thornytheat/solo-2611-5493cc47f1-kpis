<template>
  <AppShell>
    <PageHeader
      eyebrow="复核与归因 · 渠道回本排行"
      title="渠道对比"
      subtitle="按 CAC / 月均毛利贡献排回本周期；数据来自最新已发布的测算报告，低样本渠道不参与排行。"
    >
      <template #actions>
        <button class="btn btn--quiet" type="button" :disabled="!canExport" data-test="export-csv" @click="exportCsv">
          导出 CSV
        </button>
        <button class="btn" type="button" :disabled="!canExport" data-test="export-md" @click="exportMd">
          导出 MD 说明
        </button>
      </template>
    </PageHeader>

    <ErrorNotice v-if="error" :message="error" @retry="load" />
    <ErrorNotice v-if="exportError" title="导出失败" :message="exportError" :retryable="false" />

    <div v-if="loading && !data" class="skeleton"></div>

    <EmptyState v-else-if="!data" title="还没有渠道对比" :hint="EMPTY_HINTS.channels">
      <RouterLink to="/ltv" class="btn">去 LTV 测算</RouterLink>
    </EmptyState>

    <template v-else>
      <section class="source">
        <div class="source__left">
          <span class="tag" :class="data.source === 'published' ? 'tag--ok' : 'tag--warn'">
            {{ data.source === 'published' ? '已发布口径' : '现场测算' }}
          </span>
          <span v-if="data.stale" class="tag tag--warn" data-test="channel-stale">
            数据过期 · 待新版本接管
          </span>
          <span class="source__name serif">
            {{ data.report_name }}
            <template v-if="data.report_version_no"> · v{{ data.report_version_no }}</template>
          </span>
          <span class="source__meta mono" v-if="data.published_at">发布 {{ relativeDate(data.published_at) }}</span>
        </div>
        <div class="source__right mono">
          <span>报告数据 v{{ data.source_data_seq }} / 当前 v{{ data.current_data_seq }}</span>
          <span>·</span>
          <span>λ {{ data.fit.lambda.toFixed(3) }}</span>
          <span>·</span>
          <span>R² {{ data.fit.r2.toFixed(2) }}</span>
          <span>·</span>
          <span>毛利率 {{ (data.margin_rate * 100).toFixed(0) }}%</span>
        </div>
      </section>

      <div v-if="data.stale" class="scope scope--stale">
        当前渠道排行与导出仍冻结在已发布的旧口径（数据 v{{ data.source_data_seq }}）；
        源数据已更新到 v{{ data.current_data_seq }}，请在 LTV 测算页重算并发布新版本后切换。
      </div>

      <div v-if="data.scope.scoped" class="scope">
        只读账号只看到自己渠道：<strong>{{ scopeLabel }}</strong>
        ；全渠道数据请用分析师或负责人账号登录。
      </div>

      <div class="layout">
        <section class="board">
          <div class="board__head">
            <span class="board__col">排名 / 渠道</span>
            <span class="board__col right">CAC</span>
            <span class="board__col right">月均毛利</span>
            <span class="board__col right">回本</span>
            <span class="board__col right">预测 12 月 LTV</span>
          </div>
          <div
            v-for="row in data.rows"
            :key="row.channel"
            class="board__row rise"
            :data-test="`channel-${row.channel}`"
          >
            <span class="board__rank mono">{{ String(row.rank).padStart(2, '0') }}</span>
            <div class="board__name">
              <span class="board__label">{{ row.label }}</span>
              <span class="board__note">{{ row.note }}</span>
            </div>
            <span class="mono board__num">{{ money(row.cac) }}</span>
            <span class="mono board__num">{{ money(row.monthly_margin, 2) }}</span>
            <span class="mono board__num board__num--payback" :class="{ 'is-slow': row.payback_months > 4 }">
              {{ row.payback_months.toFixed(1) }} 月
            </span>
            <span class="mono board__num">{{ money(row.ltv_pred12) }}</span>
          </div>
          <div class="board__foot mono">
            <span>加权 CAC {{ money(data.totals.weighted_cac) }}</span>
            <span>样本 {{ integer(data.totals.members) }} 会员</span>
            <span>最快 {{ data.totals.best_payback?.toFixed(1) }} 月</span>
          </div>
        </section>

        <aside class="stack">
          <section class="panel panel--tight">
            <div class="eyebrow">回本周期（越短越好）</div>
            <PaybackBars :rows="data.rows" />
          </section>

          <section class="panel panel--tight">
            <div class="eyebrow">对照</div>
            <dl class="cmp">
              <div>
                <dt>历史 LTV</dt>
                <dd class="mono">{{ money(data.ltv_hist) }}</dd>
              </div>
              <div>
                <dt>预测 12 月</dt>
                <dd class="mono">{{ money(data.ltv_pred12) }}</dd>
              </div>
              <div>
                <dt>ARPU₀</dt>
                <dd class="mono">{{ money(data.arpu0) }}</dd>
              </div>
              <div>
                <dt>旧口径</dt>
                <dd class="mono">¥256（32 × 8 次）</dd>
              </div>
            </dl>
            <p class="note">{{ data.notes.payback }}</p>
          </section>

          <section class="panel panel--tight">
            <div class="eyebrow">低样本剔除</div>
            <ul class="low" v-if="data.low_sample.channel_cells.length">
              <li v-for="cell in data.low_sample.channel_cells" :key="`${cell.month}-${cell.channel}`">
                <span class="mono">{{ cell.month }}</span>
                <span>{{ channelName(cell.channel) }}</span>
                <span class="mono">{{ cell.members }} 人</span>
              </li>
            </ul>
            <p class="note" v-else>没有低于 30 人的「群×渠道」样本。</p>
            <p class="note">{{ data.notes.low_sample }}</p>
          </section>
        </aside>
      </div>
    </template>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import PaybackBars from '../components/business/PaybackBars.vue'
import { useAuthStore } from '../stores/authStore'
import { downloadChannelsCsv, downloadReportMd, fetchComparison } from '../api/channel'
import type { ChannelComparison } from '../types/domain'
import { CHANNEL_LABELS, type ChannelCode } from '../constants/enums'
import { EMPTY_HINTS } from '../constants/messages'
import { integer, money, relativeDate } from '../utils/format'

const auth = useAuthStore()
const data = ref<ChannelComparison | null>(null)
const loading = ref(false)
const error = ref('')
const exportError = ref('')

const canExport = computed(() => auth.can('channels:export'))
const scopeLabel = computed(() => {
  const scope = data.value?.scope.channel_scope
  return scope ? CHANNEL_LABELS[scope as ChannelCode] ?? scope : '—'
})

function channelName(code: string): string {
  return CHANNEL_LABELS[code as ChannelCode] ?? code
}

function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

async function exportCsv() {
  exportError.value = ''
  try {
    const blob = await downloadChannelsCsv(data.value?.report_id ?? undefined)
    saveBlob(blob, `cohortltv-channels-${data.value?.snapshot_month ?? 'snapshot'}.csv`)
  } catch (err) {
    exportError.value = (err as { message?: string }).message ?? '导出失败'
  }
}

async function exportMd() {
  exportError.value = ''
  try {
    const blob = await downloadReportMd(data.value?.report_id ?? undefined)
    saveBlob(blob, `cohortltv-report-${data.value?.snapshot_month ?? 'snapshot'}.md`)
  } catch (err) {
    exportError.value = (err as { message?: string }).message ?? '导出失败'
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await fetchComparison()
  } catch (err) {
    error.value = (err as { message?: string }).message ?? '渠道对比读取失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.source {
  display: flex; align-items: center; justify-content: space-between; gap: 12px;
  padding: 9px 14px; border: var(--hair); background: var(--cream-3); flex-wrap: wrap;
}
.source__left { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.source__name { font-size: 14px; }
.source__meta { font-size: 10px; color: var(--coffee-3); }
.source__right { display: flex; gap: 6px; font-size: 10px; color: var(--coffee-3); }

.scope {
  margin-top: 12px; border: 1px dashed var(--coffee-3); background: var(--cream-2);
  padding: 9px 12px; font-size: 12px; color: var(--coffee-2);
}
.scope--stale { border-color: var(--brick); background: var(--brick-soft); }

.layout {
  display: grid; grid-template-columns: minmax(0, 1.75fr) minmax(280px, 1fr);
  gap: 16px; align-items: start; margin-top: 14px;
}
.board { border: var(--hair); background: var(--cream-2); }
.board__head, .board__row {
  display: grid;
  grid-template-columns: 30px minmax(0, 1fr) 74px 86px 68px 96px;
  gap: 10px; align-items: center;
  padding: 8px 12px;
}
.board__head {
  border-bottom: var(--hair); font-family: var(--mono); font-size: 10px;
  letter-spacing: 0.08em; color: var(--coffee-3); text-transform: uppercase;
}
.board__col.right { text-align: right; }
.board__row { border-bottom: 1px dashed var(--rule-soft); transition: background-color 200ms var(--ease); }
.board__row:hover { background: var(--cream-3); }
.board__rank { font-size: 12px; color: var(--coffee-3); }
.board__name { display: flex; flex-direction: column; min-width: 0; }
.board__label { font-size: 13px; }
.board__note { font-size: 10px; color: var(--coffee-3); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.board__num { text-align: right; font-size: 12px; }
.board__num--payback { font-size: 13px; }
.board__num--payback.is-slow { color: var(--brick); }
.board__foot {
  display: flex; gap: 14px; flex-wrap: wrap;
  padding: 8px 12px; border-top: var(--hair);
  font-size: 10px; color: var(--coffee-3);
}

.cmp { margin: 8px 0 0; display: flex; flex-direction: column; gap: 6px; }
.cmp div { display: flex; justify-content: space-between; gap: 10px; border-bottom: 1px dotted var(--rule-soft); padding-bottom: 4px; }
.cmp dt { font-size: 11.5px; color: var(--coffee-2); }
.cmp dd { margin: 0; font-size: 12px; }
.note { margin: 8px 0 0; font-size: 10.5px; color: var(--coffee-3); line-height: 1.5; }
.low { list-style: none; margin: 6px 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.low li { display: grid; grid-template-columns: 70px 1fr auto; gap: 8px; font-size: 11px; color: var(--coffee-2); }
.skeleton { height: 280px; border: 1px dashed var(--rule); background: var(--cream-2); }

@media (max-width: 1199px) {
  .layout { grid-template-columns: 1fr; }
}
@media (max-width: 899px) {
  .board__head { display: none; }
  .board__row { grid-template-columns: 24px minmax(0, 1fr) 70px 70px; row-gap: 2px; }
  .board__num:nth-of-type(2) { display: none; }
}
</style>
