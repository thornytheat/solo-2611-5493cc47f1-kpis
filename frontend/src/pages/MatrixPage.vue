<template>
  <AppShell>
    <PageHeader
      eyebrow="算法 1 · 同期群留存矩阵"
      title="留存矩阵"
      subtitle="按首单月分群，M0 为全员活跃；观察期未到的格子标灰不参与拟合。点任意群进入详情看曲线与金额分布。"
    >
      <template #actions>
        <button
          class="btn"
          type="button"
          data-test="rebuild"
          :disabled="cohorts.rebuilding || !canRebuild"
          :title="canRebuild ? '重建矩阵（Celery worker 执行）' : '当前角色无重建权限'"
          @click="rebuild"
        >
          {{ cohorts.rebuilding ? '重建中…' : '重建矩阵' }}
        </button>
        <RouterLink to="/ltv" class="btn btn--solid" data-test="to-ltv">运行 LTV 测算</RouterLink>
      </template>
    </PageHeader>

    <ErrorNotice v-if="cohorts.error" :message="cohorts.error" @retry="load" />

    <div v-if="cohorts.loading && !cohorts.matrix" class="stack">
      <div class="skeleton"></div>
      <div class="skeleton skeleton--tall"></div>
    </div>

    <EmptyState
      v-else-if="!cohorts.hasData"
      title="矩阵还是空的"
      :hint="EMPTY_HINTS.matrix"
    >
      <button class="btn" type="button" :disabled="cohorts.rebuilding" @click="rebuild">重建矩阵</button>
    </EmptyState>

    <template v-else-if="matrix">
      <section class="band">
        <div class="band__cell">
          <span class="label">同期群</span>
          <span class="band__value mono">{{ matrix.stats.cohorts }}</span>
          <span class="band__sub mono">2025-11 → 2026-10</span>
        </div>
        <div class="band__cell">
          <span class="label">订单事实</span>
          <span class="band__value mono">{{ integer(matrix.stats.orders) }}</span>
          <span class="band__sub mono">{{ integer(matrix.stats.members) }} 会员</span>
        </div>
        <div class="band__cell">
          <span class="label">有效 / 总格</span>
          <span class="band__value mono">{{ matrix.stats.cells_observed }}<span class="band__den">/{{ matrix.stats.cells_total }}</span></span>
          <span class="band__sub mono">右删失 {{ matrix.stats.cells_censored }} 格</span>
        </div>
        <div class="band__cell">
          <span class="label">累计人均营收</span>
          <span class="band__value mono">{{ money(matrix.stats.cumulative_arpu) }}</span>
          <span class="band__sub mono">含礼盒/咖啡豆品类</span>
        </div>
        <div class="band__cell band__cell--note">
          <span class="label">快照口径</span>
          <span class="band__value mono">{{ matrix.snapshot_month }}-30</span>
          <span class="band__sub mono">M0..M{{ matrix.months - 1 }}</span>
        </div>
      </section>

      <div class="layout">
        <RetentionHeatTable :payload="matrix" :highlight="focusMonth" @select="openCohort" />

        <aside class="side stack">
          <section class="panel panel--tight">
            <div class="spread">
              <span class="eyebrow">群清单</span>
              <span class="label">{{ cohorts.cohorts.length }} 群</span>
            </div>
            <ul class="cohorts">
              <li v-for="row in recentCohorts" :key="row.month">
                <RouterLink :to="`/cohorts/${row.month}`" class="cohort">
                  <span class="cohort__month mono">{{ row.month }}</span>
                  <span class="cohort__size mono">{{ row.size }} 人</span>
                  <span class="cohort__arpu mono">{{ money(row.arpu) }}</span>
                </RouterLink>
              </li>
            </ul>
            <p class="side__note">人均累计营收 = 该群观察期累计营收 / 群规模。</p>
          </section>

          <section class="panel panel--tight">
            <div class="eyebrow">口径提示</div>
            <dl class="defs">
              <div>
                <dt>M0</dt>
                <dd>{{ matrix.notes.matrix }}</dd>
              </div>
              <div>
                <dt>右删失</dt>
                <dd>{{ matrix.notes.censor }}</dd>
              </div>
              <div>
                <dt>低样本</dt>
                <dd>{{ matrix.notes.low_sample }}</dd>
              </div>
            </dl>
          </section>

          <section class="panel panel--tight job" v-if="cohorts.job">
            <div class="eyebrow">最近一次重建</div>
            <div class="job__row mono">
              <span>{{ cohorts.job.job_id }}</span>
              <span :class="['job__status', `is-${cohorts.job.status}`]">{{ jobLabel }}</span>
            </div>
            <p class="side__note" v-if="cohorts.job.summary">
              {{ cohorts.job.summary.cells }} 格 · 有效 {{ cohorts.job.summary.cells_observed }} ·
              删失 {{ cohorts.job.summary.cells_censored }}
              <span v-if="cohorts.job.elapsed_ms"> · {{ cohorts.job.elapsed_ms }}ms</span>
            </p>
          </section>
        </aside>
      </div>
    </template>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import AppShell from '../components/common/AppShell.vue'
import PageHeader from '../components/common/PageHeader.vue'
import EmptyState from '../components/common/EmptyState.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import RetentionHeatTable from '../components/business/RetentionHeatTable.vue'
import { useCohortStore } from '../stores/cohortStore'
import { useAuthStore } from '../stores/authStore'
import { EMPTY_HINTS } from '../constants/messages'
import { JOB_STATUS_LABELS } from '../constants/enums'
import { integer, money } from '../utils/format'

const cohorts = useCohortStore()
const auth = useAuthStore()
const router = useRouter()
const focusMonth = ref<string | null>(null)

const matrix = computed(() => cohorts.matrix)
const canRebuild = computed(() => auth.can('matrix:rebuild'))
const recentCohorts = computed(() => [...cohorts.cohorts].slice(-5).reverse())
const jobLabel = computed(() => JOB_STATUS_LABELS[cohorts.job?.status ?? ''] ?? cohorts.job?.status ?? '')

async function load() {
  await cohorts.load()
}

async function rebuild() {
  try {
    await cohorts.rebuild()
  } catch {
    /* store.error 已带信息 */
  }
}

function openCohort(month: string) {
  focusMonth.value = month
  router.push(`/cohorts/${month}`)
}

onMounted(load)
</script>

<style scoped>
.band {
  display: grid;
  grid-template-columns: repeat(5, minmax(0, 1fr));
  border: var(--hair);
  border-bottom: 0;
  background: var(--cream-2);
}
.band__cell {
  display: flex; flex-direction: column; gap: 1px;
  padding: 9px 14px;
  border-right: var(--hair);
}
.band__cell:last-child { border-right: 0; }
.band__cell--note { background: var(--cream-3); }
.band__value { font-size: 20px; color: var(--espresso); }
.band__den { font-size: 12px; color: var(--coffee-3); }
.band__sub { font-size: 10px; color: var(--coffee-3); }

.layout {
  display: grid;
  grid-template-columns: minmax(0, 3.1fr) minmax(264px, 1fr);
  gap: 16px;
  align-items: start;
  margin-top: 16px;
}
.side { min-width: 0; }
.side__note { margin: 8px 0 0; font-size: 10.5px; color: var(--coffee-3); line-height: 1.5; }

.cohorts { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; }
.cohort {
  display: grid; grid-template-columns: 1fr auto auto;
  gap: 10px; align-items: baseline;
  padding: 6px 0;
  border-bottom: 1px dashed var(--rule-soft);
  transition: color 200ms var(--ease), transform 200ms var(--ease);
}
.cohort:hover { color: var(--coffee); transform: translateX(2px); }
.cohort__month { font-size: 12px; }
.cohort__size { font-size: 10px; color: var(--coffee-3); }
.cohort__arpu { font-size: 11px; color: var(--coffee-2); }

.defs { margin: 8px 0 0; display: flex; flex-direction: column; gap: 9px; }
.defs div { display: grid; grid-template-columns: 56px 1fr; gap: 8px; }
.defs dt { font-family: var(--mono); font-size: 10px; color: var(--coffee); }
.defs dd { margin: 0; font-size: 11px; color: var(--coffee-2); line-height: 1.5; }

.job__row { display: flex; justify-content: space-between; gap: 8px; font-size: 11px; margin-top: 6px; }
.job__status { font-size: 10px; }
.job__status.is-succeeded { color: var(--sage); }
.job__status.is-failed { color: var(--brick); }
.job__status.is-running, .job__status.is-queued { color: var(--gold); }

.skeleton {
  height: 90px; border: 1px dashed var(--rule); background: var(--cream-2);
  animation: pulse 1.4s ease-in-out infinite;
}
.skeleton--tall { height: 340px; }
@keyframes pulse { 0%, 100% { opacity: 0.55; } 50% { opacity: 0.9; } }

@media (max-width: 1199px) {
  .layout { grid-template-columns: 1fr; }
  .band { grid-template-columns: repeat(3, minmax(0, 1fr)); }
  .band__cell:nth-child(3) { border-right: 0; }
}
@media (max-width: 767px) {
  .band { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .band__cell { border-bottom: var(--hair); }
  .band__cell--note { display: none; }
  .cohort { grid-template-columns: 1fr auto; }
  .cohort__size { display: none; }
}
</style>
