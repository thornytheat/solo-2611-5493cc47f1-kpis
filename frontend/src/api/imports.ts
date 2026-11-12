import http from './http'
import type { DataVersion, ImportBatch, ImportPayload, ImportResult } from '../types/domain'

export async function importOrders(payload: ImportPayload): Promise<ImportResult> {
  const { data } = await http.post<ImportResult>('/orders/import', payload)
  return data
}

export async function fetchImportBatches(): Promise<ImportBatch[]> {
  const { data } = await http.get<ImportBatch[]>('/orders/import/batches')
  return data
}

export async function fetchDataVersions(): Promise<DataVersion[]> {
  const { data } = await http.get<DataVersion[]>('/data-versions')
  return data
}

export async function fetchCurrentVersion(): Promise<DataVersion> {
  const { data } = await http.get<DataVersion>('/data-versions/current')
  return data
}
