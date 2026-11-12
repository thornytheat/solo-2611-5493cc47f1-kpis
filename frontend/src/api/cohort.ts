import http from './http'
import type { JobStatusPayload } from '../types/api'
import type { CohortDetail, CohortSummary, MatrixPayload } from '../types/domain'

export async function fetchMatrix(): Promise<MatrixPayload> {
  const { data } = await http.get<MatrixPayload>('/matrix')
  return data
}

export async function fetchCohorts(): Promise<{ total: number; items: CohortSummary[]; snapshot_month: string }> {
  const { data } = await http.get('/cohorts')
  return data
}

export async function fetchCohortDetail(month: string): Promise<CohortDetail> {
  const { data } = await http.get<CohortDetail>(`/cohorts/${month}`)
  return data
}

export async function rebuildMatrix(payload: { snapshot_month?: string; months?: number }): Promise<JobStatusPayload> {
  const { data } = await http.post<JobStatusPayload>('/cohorts/rebuild', payload)
  return data
}

export async function fetchRebuildStatus(jobId: string): Promise<JobStatusPayload> {
  const { data } = await http.get<JobStatusPayload>(`/cohorts/rebuild/${jobId}`)
  return data
}
