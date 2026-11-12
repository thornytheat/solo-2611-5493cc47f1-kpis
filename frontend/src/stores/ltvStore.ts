import { defineStore } from 'pinia'
import {
  fetchReport,
  fetchReports,
  fetchSensitivity,
  publishReport,
  recomputeReport,
  runReport,
  type RunPayload,
} from '../api/ltv'
import type { LtvReport, LtvReportSummary, SensitivityPayload } from '../types/domain'

interface LtvState {
  reports: LtvReportSummary[]
  current: LtvReport | null
  sensitivity: SensitivityPayload | null
  loading: boolean
  running: boolean
  publishing: boolean
  recomputing: boolean
  error: string
}

export const useLtvStore = defineStore('ltv', {
  state: (): LtvState => ({
    reports: [],
    current: null,
    sensitivity: null,
    loading: false,
    running: false,
    publishing: false,
    recomputing: false,
    error: '',
  }),
  getters: {
    results: (state) => state.current?.results ?? null,
    fit: (state) => state.current?.results?.fit ?? null,
    isPublished: (state): boolean => state.current?.status === 'published',
    isStale: (state): boolean => state.current?.stale ?? false,
    reviewState: (state): string => state.current?.review_state ?? 'draft',
  },
  actions: {
    async loadReports() {
      this.loading = true
      this.error = ''
      try {
        const payload = await fetchReports()
        this.reports = payload.items
        if (payload.items.length && !this.current) {
          await this.open(payload.items[0].id)
        }
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '加载报告失败'
      } finally {
        this.loading = false
      }
    },
    async open(reportId: string) {
      try {
        this.current = await fetchReport(reportId)
        this.sensitivity = null
        if (this.current.status === 'published' || this.current.results) {
          try {
            this.sensitivity = await fetchSensitivity(reportId)
          } catch {
            this.sensitivity = null
          }
        }
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '报告读取失败'
      }
    },
    async run(payload: RunPayload) {
      this.running = true
      this.error = ''
      try {
        const report = await runReport(payload)
        this.current = report
        await this.loadReports()
        await this.open(report.id)
        return report
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '测算失败'
        throw error
      } finally {
        this.running = false
      }
    },
    async publish() {
      if (!this.current) return
      this.publishing = true
      this.error = ''
      try {
        const report = await publishReport(this.current.id)
        this.current = report
        await this.loadReports()
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '发布失败'
        throw error
      } finally {
        this.publishing = false
      }
    },
    async recompute() {
      if (!this.current) return
      this.recomputing = true
      this.error = ''
      try {
        const report = await recomputeReport(this.current.id)
        this.current = report
        await this.loadReports()
        await this.open(report.id)
        return report
      } catch (error) {
        this.error = (error as { message?: string }).message ?? '重算失败'
        throw error
      } finally {
        this.recomputing = false
      }
    },
  },
})
