<template>
  <AppShell>
    <PageHeader
      eyebrow="数据治理 · 订单补录与更正"
      title="订单导入"
      subtitle="整批校验通过后订单、留存矩阵、渠道回本与导出口径在同一事务切换；任一错误整批不动，页面继续展示上一版。"
    >
      <template #actions>
        <span class="tag" :class="currentVersion ? 'tag--ok' : 'tag--warn'">
          当前数据 {{ currentVersion ? `v${currentVersion.seq}` : '未初始化' }}
        </span>
      </template>
    </PageHeader>

    <ErrorNotice v-if="error" :message="error" @retry="loadMeta" />

    <div class="layout">
      <form class="panel form" @submit.prevent="submit">
        <div class="eyebrow">批次信息</div>
        <label class="field">
          <span class="label">外部批次号（唯一，重复导入不新增）</span>
          <input v-model="batchNo" type="text" placeholder="如 BATCH-20261112-01" data-test="import-batch-no" />
        </label>
        <div class="form__pair">
          <label class="field">
            <span class="label">依据版本序号（可选）</span>
            <input
              v-model.number="sourceSeq"
              type="number"
              min="1"
              :placeholder="currentVersion ? `当前 v${currentVersion.seq}` : '1'"
              data-test="import-source-seq"
            />
          </label>
          <label class="field field--check">
            <input v-model="dryRun" type="checkbox" data-test="import-dry-run" />
            <span class="label">只校验不切换（dry-run）</span>
          </label>
        </div>
        <label class="field">
          <span class="label">备注</span>
          <input v-model="note" type="text" placeholder="如 11 月订单更正：MO.. 金额调整" />
        </label>

        <label class="field">
          <div class="spread">
            <span class="label">订单行（JSON 数组，单次最多 {{ maxRows }} 行）</span>
            <button class="btn btn--sm btn--quiet" type="button" @click="fillExample">填入示例</button>
          </div>
          <textarea
            v-model="rawJson"
            class="form__json mono"
            rows="12"
            spellcheck="false"
            placeholder='[{"order_no":"MO001","member_code":"M01-0001","cohort_month":"2026-10","order_month":"2026-10","channel":"private","amount":32.5}]'
            data-test="import-json"
          ></textarea>
        </label>

        <p v-if="parseError" class="form__error">{{ parseError }}</p>

        <div class="form__actions">
          <button
            class="btn btn--solid"
            type="submit"
            :disabled="submitting || !canImport || !rawJson.trim()"
            data-test="import-submit"
          >
            {{ submitting ? '处理中…' : dryRun ? '整批校验' : '校验并切换版本' }}
          </button>
          <button class="btn btn--quiet" type="button" :disabled="submitting" @click="resetForm">清空</button>
        </div>
        <p class="form__hint mono">
          同订单号走更正不新增 · 晚到旧批次（序号 ≤ 当前版本）拒绝 · 失败零写入
        </p>
      </form>

      <div class="stack grow">
        <section v-if="lastResult" class="panel panel--tight result" :class="resultTone">
          <div class="spread">
            <div class="eyebrow">最近一次处理结果</div>
            <span class="tag" :class="resultTagClass">{{ resultStatusLabel }}</span>
          </div>
          <div class="result__grid">
            <div class="kpi"><span class="label">总行数</span><span class="kpi__value mono">{{ lastResult.row_count }}</span></div>
            <div class="kpi"><span class="label">新增</span><span class="kpi__value mono" data-test="result-inserted">{{ lastResult.inserted }}</span></div>
            <div class="kpi"><span class="label">更正</span><span class="kpi__value mono" data-test="result-updated">{{ lastResult.updated }}</span></div>
            <div class="kpi"><span class="label">无变化</span><span class="kpi__value mono">{{ lastResult.unchanged }}</span></div>
          </div>
          <p v-if="lastResult.batch_seq" class="result__note">
            已激活新版本 <strong>v{{ lastResult.batch_seq }}</strong>，留存矩阵已在同事务重建
            （{{ lastResult.matrix?.cells ?? '—' }} 格）。
          </p>
          <p v-if="lastResult.would_activate_seq" class="result__note">
            校验通过，正式提交后将激活 v{{ lastResult.would_activate_seq }}；当前未写任何数据。
          </p>
          <ul v-if="lastResult.errors.length" class="errors">
            <li v-for="(item, i) in lastResult.errors" :key="i" class="errors__item">
              <span class="mono">#{{ item.index }} {{ item.order_no || '—' }}</span>
              <span>{{ item.field }}：{{ item.message }}</span>
            </li>
          </ul>
        </section>

        <section class="panel panel--tight">
          <div class="spread">
            <div class="eyebrow">数据版本（口径切换边界）</div>
            <span class="label">{{ versions.length }} 个版本</span>
          </div>
          <table class="table">
            <thead>
              <tr>
                <th>版本</th>
                <th>说明</th>
                <th class="num">订单</th>
                <th class="num">会员</th>
                <th class="num">留存格</th>
                <th>激活时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="version in versions" :key="version.id" :class="{ 'is-current': version.seq === currentVersion?.seq }">
                <td class="mono">v{{ version.seq }}</td>
                <td>{{ version.label }}<div class="row-note">{{ version.change_note }}</div></td>
                <td class="num mono">{{ integer(version.orders_count) }}</td>
                <td class="num mono">{{ integer(version.members_count) }}</td>
                <td class="num mono">{{ integer(version.cells_count) }}</td>
                <td class="mono">{{ shortTime(version.activated_at) }}</td>
              </tr>
            </tbody>
          </table>
        </section>

        <section class="panel panel--tight">
          <div class="spread">
            <div class="eyebrow">导入批次留痕</div>
            <span class="label">全状态可追溯</span>
          </div>
          <table class="table">
            <thead>
              <tr>
                <th>批次号</th>
                <th>状态</th>
                <th class="num">行</th>
                <th class="num">新增/更正</th>
                <th class="num">拒绝</th>
                <th>时间</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="batch in batches" :key="batch.id">
                <td class="mono batch-no">{{ batch.batch_no }}</td>
                <td><span class="tag" :class="batchTagClass(batch.status)">{{ batchStatusLabel(batch.status) }}</span></td>
                <td class="num mono">{{ batch.row_count }}</td>
                <td class="num mono">{{ batch.inserted_count }} / {{ batch.updated_count }}</td>
                <td class="num mono">{{ batch.rejected_count }}</td>
                <td class="mono">{{ shortTime(batch.applied_at || batch.created_at) }}</td>
              </tr>
            </tbody>
          </table>
        </section>
      </div>
    </div>
  </AppShell>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import AppShell from '../components/common/AppShell.vue'
import PageHeader from '../components/common/PageHeader.vue'
import ErrorNotice from '../components/common/ErrorNotice.vue'
import { useAuthStore } from '../stores/authStore'
import { fetchDataVersions, fetchImportBatches, importOrders } from '../api/imports'
import type { DataVersion, ImportBatch, ImportOrderRow, ImportResult } from '../types/domain'
import { IMPORT_BATCH_STATUS_LABELS } from '../constants/enums'
import { integer } from '../utils/format'

const auth = useAuthStore()
const maxRows = 5000

const batchNo = ref('')
const sourceSeq = ref<number | null>(null)
const dryRun = ref(false)
const note = ref('')
const rawJson = ref('')
const parseError = ref('')
const submitting = ref(false)
const error = ref('')
const lastResult = ref<ImportResult | null>(null)
const versions = ref<DataVersion[]>([])
const batches = ref<ImportBatch[]>([])

const currentVersion = computed(() => versions.value[0] ?? null)
const canImport = computed(() => auth.can('orders:import'))

const resultTone = computed(() => {
  if (!lastResult.value) return ''
  return lastResult.value.status === 'failed' || lastResult.value.rejected_count > 0
    ? 'result--bad'
    : 'result--ok'
})
const resultTagClass = computed(() => (resultTone.value === 'result--bad' ? 'tag--warn' : 'tag--ok'))
const resultStatusLabel = computed(() =>
  lastResult.value ? IMPORT_BATCH_STATUS_LABELS[lastResult.value.status] ?? lastResult.value.status : '',
)

function shortTime(value: string | null): string {
  if (!value) return '—'
  return value.replace('T', ' ').slice(0, 16)
}

function batchStatusLabel(status: string): string {
  return IMPORT_BATCH_STATUS_LABELS[status] ?? status
}

function batchTagClass(status: string): string {
  if (status === 'applied') return 'tag--ok'
  if (status === 'validated') return 'tag--info'
  return 'tag--warn'
}

function fillExample() {
  const seq = currentVersion.value ? currentVersion.value.seq + 1 : 1
  sourceSeq.value = currentVersion.value ? currentVersion.value.seq : null
  batchNo.value = `BATCH-${Date.now()}`
  rawJson.value = JSON.stringify(
    [
      {
        order_no: 'MO-CORRECT-01',
        member_code: 'M01-0001',
        cohort_month: '2026-10',
        order_month: '2026-10',
        channel: 'private',
        amount: 35.8,
        store_code: 'MY001',
        is_first_order: true,
      },
    ],
    null,
    2,
  )
  note.value = `示例：补录/更正批次，正式提交后激活 v${seq}`
  parseError.value = ''
}

function parseRows(): ImportOrderRow[] | null {
  parseError.value = ''
  try {
    const data = JSON.parse(rawJson.value)
    if (!Array.isArray(data)) {
      parseError.value = '订单行必须是 JSON 数组'
      return null
    }
    if (data.length === 0) {
      parseError.value = '批次不能为空（至少 1 行）'
      return null
    }
    if (data.length > maxRows) {
      parseError.value = `单批最多 ${maxRows} 行，当前 ${data.length} 行`
      return null
    }
    return data as ImportOrderRow[]
  } catch (err) {
    parseError.value = `JSON 解析失败：${(err as Error).message}`
    return null
  }
}

async function submit() {
  const rows = parseRows()
  if (!rows || !batchNo.value.trim()) {
    if (!batchNo.value.trim()) parseError.value = '批次号不能为空'
    return
  }
  submitting.value = true
  error.value = ''
  try {
    lastResult.value = await importOrders({
      batch_no: batchNo.value.trim(),
      source_seq: sourceSeq.value,
      dry_run: dryRun.value,
      note: note.value,
      rows,
    })
    await loadMeta()
  } catch (err) {
    const e = err as { message?: string; extra?: { errors?: ImportResult['errors']; batch_id?: string } }
    error.value = e.message ?? '导入失败'
    if (e.extra?.errors?.length) {
      lastResult.value = {
        batch_id: e.extra.batch_id ?? '',
        batch_no: batchNo.value.trim(),
        status: 'failed',
        dry_run: dryRun.value,
        batch_seq: null,
        data_version_id: null,
        row_count: rows.length,
        inserted: 0,
        updated: 0,
        unchanged: 0,
        rejected_count: e.extra.errors.length,
        errors: e.extra.errors,
      }
    }
  } finally {
    submitting.value = false
  }
}

function resetForm() {
  batchNo.value = ''
  sourceSeq.value = null
  dryRun.value = false
  note.value = ''
  rawJson.value = ''
  parseError.value = ''
  lastResult.value = null
}

async function loadMeta() {
  try {
    const [versionRows, batchRows] = await Promise.all([fetchDataVersions(), fetchImportBatches()])
    versions.value = versionRows
    batches.value = batchRows
  } catch (err) {
    error.value = (err as { message?: string }).message ?? '版本/批次加载失败'
  }
}

onMounted(loadMeta)
</script>

<style scoped>
.layout {
  display: grid; grid-template-columns: minmax(280px, 360px) minmax(0, 1fr);
  gap: 16px; align-items: start;
}
.form { display: flex; flex-direction: column; gap: 12px; }
.form__pair { display: grid; grid-template-columns: 1fr auto; gap: 10px; align-items: end; }
.field--check { display: flex; align-items: center; gap: 6px; padding-bottom: 6px; }
.form__json {
  width: 100%; min-height: 220px; border: 1px solid var(--rule); background: var(--cream-2);
  padding: 8px 10px; font-family: var(--mono); font-size: 11px; line-height: 1.55; resize: vertical;
}
.form__actions { display: flex; gap: 8px; }
.form__hint { margin: 0; font-size: 9.5px; color: var(--coffee-3); line-height: 1.6; }
.form__error { margin: 0; color: var(--brick); font-size: 11px; }

.result { border-left: 3px solid var(--coffee-3); }
.result--ok { border-left-color: #3f7a4f; }
.result--bad { border-left-color: var(--brick); }
.result__grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; margin: 10px 0; }
.kpi { display: flex; flex-direction: column; gap: 2px; }
.kpi__value { font-size: 1.4rem; }
.result__note { font-size: 11px; color: var(--coffee-2); margin: 6px 0 0; }
.errors { list-style: none; margin: 8px 0 0; padding: 0; display: flex; flex-direction: column; gap: 4px; }
.errors__item {
  display: flex; gap: 8px; font-size: 11px; color: var(--brick);
  border: 1px dashed var(--rule); padding: 5px 8px; background: var(--cream-2);
}
.table { width: 100%; border-collapse: collapse; font-size: 11.5px; }
.table th {
  text-align: left; font-family: var(--mono); font-size: 9.5px; letter-spacing: 0.06em;
  color: var(--coffee-3); text-transform: uppercase; padding: 6px 8px; border-bottom: var(--hair);
}
.table td { padding: 7px 8px; border-bottom: 1px dashed var(--rule-soft); vertical-align: top; }
.table .num { text-align: right; }
tr.is-current { background: var(--cream-3); }
.row-note { font-size: 10px; color: var(--coffee-3); margin-top: 2px; }
.batch-no { max-width: 220px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.tag--info { background: #e7eef5; color: #2f5d8a; }

@media (max-width: 1199px) {
  .layout { grid-template-columns: 1fr; }
  .result__grid { grid-template-columns: repeat(2, 1fr); }
}
</style>
