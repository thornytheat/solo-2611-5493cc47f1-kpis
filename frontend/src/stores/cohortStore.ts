import { defineStore } from 'pinia'
import { fetchCohorts, fetchMatrix, fetchRebuildStatus, rebuildMatrix } from '../api/cohort'
import type { CohortSummary, MatrixPayload } from '../types/domain'
import type { JobStatusPayload } from '../types/api'

interface CohortState {
  matrix: MatrixPayload | null
  cohorts: CohortSummary[]
  loading: boolean
  error: string
  job: JobStatusPayload | null
  rebuilding: boolean
  highlightMonth: string | null
}

export const useCohortStore = defineStore('cohort', {
  state: (): CohortState => ({
    matrix: null,
    cohorts: [],
    loading: false,
    error: '',
    job: null,
    rebuilding: false,
    highlightMonth: null,
  }),
  getters: {
    stats: (state) => state.matrix?.stats ?? null,
    snapshot: (state) => state.matrix?.snapshot_month ?? '',
    hasData: (state): boolean => Boolean(state.matrix && state.matrix.cohorts.length),
  },
  actions: {
    async load() {
      this.loading = true
      this.error = ''
      try {
        const [matrix, cohorts] = await Promise.all([fetchMatrix(), fetchCohorts()])
        this.matrix = matrix
        this.cohorts = cohorts.items
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '加载矩阵失败'
      } finally {
        this.loading = false
      }
    },
    async rebuild() {
      this.rebuilding = true
      this.error = ''
      try {
        let job = await rebuildMatrix({})
        this.job = job
        let tries = 0
        while (job.status === 'queued' || job.status === 'running') {
          if (tries >= 60) break
          tries += 1
          await new Promise((resolve) => setTimeout(resolve, 500))
          job = await fetchRebuildStatus(job.job_id)
          this.job = job
        }
        if (job.status === 'failed') {
          this.error = job.detail ?? '矩阵重建失败'
        } else if (job.status !== 'succeeded') {
          this.error = '重建任务仍在排队（worker 未消费），请稍后重试或查看容器状态'
          await this.load()
        } else {
          await this.load()
        }
        return job
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '矩阵重建失败'
        throw error
      } finally {
        this.rebuilding = false
      }
    },
    highlight(month: string | null) {
      this.highlightMonth = month
    },
  },
})
