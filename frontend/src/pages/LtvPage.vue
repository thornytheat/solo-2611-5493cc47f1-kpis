<template>
  <AppShell>
    <PageHeader
      eyebrow="算法 2 · ARPU 衰减拟合与回本"
      title="LTV 测算"
      subtitle="配置口径 → 运行测算 → 复核并发布。λ 由后端在 [0.02, 0.60] 上网格搜索，前端只展示结果。"
    >
      <template #actions>
        <span v-if="ltv.current" class="tag" :class="ltv.isPublished ? 'tag--ok' : 'tag--warn'">
          {{ REPORT_STATUS_LABELS[ltv.current.status] }}
        </span>
        <button
          class="btn btn--quiet"
          type="button"
          :disabled="!canPublish || !ltv.current || ltv.isPublished || ltv.publishing"
          data-test="publish"
          :title="canPublish ? '发布后渠道页与导出口径冻结' : '仅增长负责人可发布'"
          @click="publish"
        >
          {{ ltv.publishing ? '发布中…' : '发布报告' }}
        </button>
        <RouterLink to="/channels" class="btn btn--solid">看渠道对比</RouterLink>
      </template>
    </PageHeader>

    <ErrorNotice v-if="ltv.error" :message="ltv.error" @retry="loadReports" />

    <div class="layout">
      <form class="panel form" @submit.prevent="run">
        <div class="eyebrow">口径参数</div>
        <label class="field">
          <span class="label">报告名称</span>
          <input v-model="form.name" type="text" :placeholder="defaultName(snapshot)" data-test="ltv-name" />
        </label>
        <div class="form__pair">
          <label class="field">
            <span class="label">观察月上限</span>
            <select v-model="form.observedMonths" data-test="ltv-months">
              <option :value="null">按快照（M0..M12）</option>
              <option v-for="n in [13, 10, 8, 6]" :key="n" :value="n">M0..M{{ n - 1 }}</option>
            </select>
          </label>
          <label class="field">
            <span class="label">预测月数</span>
            <select v-model="form.forecastMonths">
              <option v-for="n in [6, 12, 18]" :key="n" :value="n">{{ n }} 个月</option>
            </select>
          </label>
        </div>
        <label class="field">
          <span class="label">毛利率（回本按毛利口径）</span>
          <input v-model.number="form.marginRate" type="number" min="0.05" max="1" step="0.01" data-test="ltv-margin" />
        </label>
        <div class="form__cac">
          <div class="spread">
            <span class="label">渠道 CAC（元 / 会员）</span>
            <button class="btn btn--sm btn--quiet" type="button" @click="resetCac">重置</button>
          </div>
          <label v-for="item in cacList" :key="item.code" class="cac">
            <span class="cac__name">{{ item.label }}</span>
            <input v-model.number="form.cac[item.code]" type="number" min="1" step="1" class="cac__input" />
          </label>
        </div>

        <button class="btn btn--solid form__run" type="submit" :disabled="ltv.running || !canRun" data-test="ltv-run">
          {{ ltv.running ? '拟合中…' : '运行测算' }}
        </button>
        <p class="form__hint mono">λ ∈ [0.02, 0.60] · step 0.001 · 权重 = 群规模</p>
      </form>

      <div class="stack grow">
        <template v-if="results">
          <section class="receipt">
            <div class="receipt__head">
              <div>
                <div class="eyebrow">测算结果 · {{ results.snapshot_month }}</div>
                <div class="receipt__name serif">{{ ltv.current?.name }}</div>
              </div>
              <StampSeal :label="ltv.isPublished ? '已发布' : '待复核'" :tone="ltv.isPublished ? 'ok' : 'warn'" size="md" />
            </div>

            <div class="receipt__grid">
              <div class="kpi">
                <span class="label">ARPU₀</span>
                <span class="kpi__value mono" data-test="arpu0">{{ money(results.arpu0) }}</span>
                <span class="kpi__sub mono">M0 人均营收</span>
              </div>
              <div class="kpi">
                <span class="label">衰减 λ</span>
                <span class="kpi__value mono" data-test="lambda">{{ results.fit.lambda.toFixed(3) }}</span>
                <span class="kpi__sub mono">R² {{ results.fit.r2.toFixed(2) }}</span>
              </div>
              <div class="kpi">
                <span class="label">历史 LTV</span>
                <span class="kpi__value mono" data-test="ltv-hist">{{ money(results.ltv_hist) }}</span>
                <span class="kpi__sub mono">观察期人均累计</span>
              </div>
              <div class="kpi kpi--accent">
                <span class="label">预测 12 月 LTV</span>
                <span class="kpi__value mono" data-test="ltv-pred">{{ money(results.ltv_pred12) }}</span>
                <span class="kpi__sub mono">×{{ results.lift_ratio.toFixed(2) }} 历史</span>
              </div>
            </div>

            <div class="receipt__meta mono">
              <span>有效格 {{ results.totals.observed_cells }}</span>
              <span>·</span>
              <span>右删失 {{ results.totals.censored_cells }}</span>
              <span>·</span>
              <span>a = {{ results.fit.a.toFixed(4) }}</span>
              <span>·</span>
              <span>毛利率 {{ (results.params.margin_rate * 100).toFixed(0) }}%</span>
            </div>

            <p class="receipt__note">{{ results.notes.fit }}</p>
          </section>

          <section class="panel panel--tight">
            <div class="spread">
              <div class="eyebrow">渠道回本（按 λ 与 CAC 结果）</div>
              <span class="label">毛利口径</span>
            </div>
            <table class="table">
              <thead>
                <tr>
                  <th>#</th>
                  <th>渠道</th>
                  <th class="num">CAC</th>
                  <th class="num">月均毛利</th>
                  <th class="num">回本</th>
                  <th class="num">预测 12 月 LTV</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="row in results.channels" :key="row.channel">
                  <td class="mono">{{ row.rank }}</td>
                  <td>{{ row.short }}</td>
                  <td class="num">{{ money(row.cac) }}</td>
                  <td class="num">{{ money(row.monthly_margin, 2) }}</td>
                  <td class="num">
                    <span :class="{ 'is-slow': row.payback_months > 4 }">{{ row.payback_months.toFixed(1) }} 月</span>
                  </td>
                  <td class="num">{{ money(row.ltv_pred12) }}</td>
                </tr>
              </tbody>
            </table>
            <p class="receipt__note">
              低样本剔除：{{ results.low_sample.channel_cells.length }} 个「群×渠道」，
              群维度 {{ results.low_sample.cohorts.length }} 个。
            </p>
          </section>

          <section v-if="ltv.sensitivity" class="panel panel--tight">
            <SensitivityTable :payload="ltv.sensitivity" />
          </section>

          <section v-if="cohorts.matrix" class="panel panel--tight">
            <RetentionHeatTable :payload="cohorts.matrix" @select="goCohort" />
          </section>
        </template>

        <EmptyState v-else title="还没有测算结果" :hint="EMPTY_HINTS.ltv">
          <button class="btn" type="button" :disabled="!canRun || ltv.running" @click="run">运行测算</button>
        </EmptyState>

        <section class="panel panel--tight" v-if="ltv.reports.length">
          <div class="spread">
            <div class="eyebrow">报告清单</div>
            <span class="label">{{ ltv.reports.length }} 份</span>
          </div>
          <ul class="reports">
            <li v-for="report in ltv.reports" :key="report.id">
              <button type="button" class="report" :class="{ 'is-active': report.id === ltv.current?.id }" @click="open(report.id)">
                <span class="report__name">{{ report.name }}</span>
                <span class="report__meta mono">
                  λ {{ report.lam?.toFixed(3) ?? '—' }} · LTV {{ money(report.ltv_pred12) }}
                </span>
                <span class="tag" :class="report.status === 'published' ? 'tag--ok' : 'tag--warn'">
                  {{ REPORT_STATUS_LABELS[report.status] }}
                </span>
              </button>
            </li>
          </ul>
          <p v-if="auth.role === 'viewer'" class="receipt__note">
            只读角色只能看到已发布报告；测算参数与敏感性表仅分析师/负责人可见。
          </p>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import StampSeal from '../components/common/StampSeal.vue'
import SensitivityTable from '../components/business/SensitivityTable.vue'
import RetentionHeatTable from '../components/business/RetentionHeatTable.vue'
import { useLtvStore } from '../stores/ltvStore'
import { useCohortStore } from '../stores/cohortStore'
import { useAuthStore } from '../stores/authStore'
import { useLtvForm } from '../hooks/useLtvForm'
import { REPORT_STATUS_LABELS } from '../constants/enums'
import { EMPTY_HINTS } from '../constants/messages'
import { money } from '../utils/format'

const ltv = useLtvStore()
const cohorts = useCohortStore()
const auth = useAuthStore()
const router = useRouter()
const { form, cacList, payload, resetCac, defaultName } = useLtvForm()

const results = computed(() => ltv.results)
const snapshot = computed(() => ltv.current?.results?.snapshot_month ?? cohorts.snapshot ?? '2026-11')
const canRun = computed(() => auth.can('ltv:run'))
const canPublish = computed(() => auth.can('ltv:publish'))

async function loadReports() {
  await ltv.loadReports()
  if (!cohorts.matrix) await cohorts.load()
}

async function run() {
  try {
    await ltv.run(payload(snapshot.value))
  } catch {
    /* store.error */
  }
}

async function publish() {
  try {
    await ltv.publish()
  } catch {
    /* store.error */
  }
}

async function open(reportId: string) {
  await ltv.open(reportId)
}

function goCohort(month: string) {
  router.push(`/cohorts/${month}`)
}

onMounted(loadReports)
</script>

<style scoped>
.layout {
  display: grid; grid-template-columns: minmax(250px, 300px) minmax(0, 1fr);
  gap: 16px; align-items: start;
}
.form { display: flex; flex-direction: column; gap: 12px; }
.form__pair { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
.form__cac { display: flex; flex-direction: column; gap: 6px; border-top: var(--hair); padding-top: 10px; }
.cac { display: grid; grid-template-columns: 1fr 76px; align-items: center; gap: 8px; }
.cac__name { font-size: 12px; }
.cac__input { border: 1px solid var(--rule); background: var(--cream-2); padding: 4px 7px; font-family: var(--mono); font-size: 11.5px; }
.form__run { justify-content: center; margin-top: 4px; }
.form__hint { margin: 0; font-size: 9.5px; color: var(--coffee-3); }

.receipt { border: 1px solid var(--coffee); background: var(--cream-2); padding: 16px 18px; }
.receipt__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; }
.receipt__name { font-size: 17px; margin-top: 2px; }
.receipt__grid {
  display: grid; grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 0; margin: 14px 0 10px;
  border-top: 1px dashed var(--rule); border-bottom: 1px dashed var(--rule);
}
.kpi { display: flex; flex-direction: column; gap: 2px; padding: 10px 12px 10px 0; }
.kpi--accent { background: var(--cream-3); padding-left: 12px; }
.kpi__value { font-size: clamp(1.4rem, 1.1rem + 1vw, 1.95rem); }
.kpi__sub { font-size: 10px; color: var(--coffee-3); }
.receipt__meta { display: flex; flex-wrap: wrap; gap: 6px; font-size: 10px; color: var(--coffee-3); }
.receipt__note { margin: 8px 0 0; font-size: 10.5px; color: var(--coffee-3); line-height: 1.5; }

.reports { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.report {
  display: grid; grid-template-columns: minmax(0, 1fr) auto auto; gap: 10px; align-items: center;
  width: 100%; text-align: left; background: transparent; border: 1px solid transparent;
  border-bottom: 1px dashed var(--rule-soft); padding: 6px 4px;
  transition: background-color 200ms var(--ease);
}
.report:hover { background: var(--cream-3); }
.report.is-active { border-color: var(--coffee-3); background: var(--cream-3); }
.report__name { font-size: 12px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.report__meta { font-size: 10px; color: var(--coffee-3); }
.is-slow { color: var(--brick); }

@media (max-width: 1199px) {
  .layout { grid-template-columns: 1fr; }
  .receipt__grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 767px) {
  .form__pair { grid-template-columns: 1fr; }
  .receipt__grid { grid-template-columns: 1fr; }
  .kpi { border-bottom: 1px dashed var(--rule-soft); }
}
</style>
