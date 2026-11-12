import http from './http'
import type { ChannelComparison } from '../types/domain'

export async function fetchComparison(): Promise<ChannelComparison> {
  const { data } = await http.get<ChannelComparison>('/channels/comparison')
  return data
}

export async function downloadChannelsCsv(reportId?: string): Promise<Blob> {
  const { data } = await http.get('/exports/channels.csv', {
    params: reportId ? { report_id: reportId } : {},
    responseType: 'blob',
  })
  return data as Blob
}

export async function downloadReportMd(reportId?: string): Promise<Blob> {
  const { data } = await http.get('/exports/report.md', {
    params: reportId ? { report_id: reportId } : {},
    responseType: 'blob',
  })
  return data as Blob
}
