import apiClient from './client'
import {
  APIResponse,
  AuditDecision,
  AuditDecisionCreateRequest,
  AuditDossier,
  AuditSelectionReason,
  AuditStatus,
  AuditSummary,
  CreateDisputeRequest,
  Dispute,
  ResolveDisputeRequest,
} from '../types'

export interface AuditQueueFilter {
  status?: AuditStatus
  selection_reason?: AuditSelectionReason
}

export async function getAuditQueue(
  filter?: AuditQueueFilter
): Promise<APIResponse<AuditSummary[]>> {
  const res = await apiClient.get<APIResponse<AuditSummary[]>>('/audits', {
    params: filter,
  })
  return res.data
}

export async function getAuditDossier(
  auditId: string
): Promise<APIResponse<AuditDossier>> {
  const res = await apiClient.get<APIResponse<AuditDossier>>(`/audits/${auditId}`)
  return res.data
}

export async function recordAuditDecision(
  auditId: string,
  payload: AuditDecisionCreateRequest
): Promise<APIResponse<AuditDecision>> {
  const res = await apiClient.post<APIResponse<AuditDecision>>(
    `/audits/${auditId}/decision`,
    payload
  )
  return res.data
}

export async function raiseProjectDispute(
  projectId: string,
  payload: CreateDisputeRequest
): Promise<APIResponse<Dispute>> {
  const res = await apiClient.post<APIResponse<Dispute>>(
    `/projects/${projectId}/dispute`,
    payload
  )
  return res.data
}

export async function listProjectDisputes(
  projectId: string
): Promise<APIResponse<Dispute[]>> {
  const res = await apiClient.get<APIResponse<Dispute[]>>(
    `/projects/${projectId}/disputes`
  )
  return res.data
}

export async function resolveDispute(
  disputeId: string,
  payload: ResolveDisputeRequest
): Promise<APIResponse<Dispute>> {
  const res = await apiClient.post<APIResponse<Dispute>>(
    `/audits/disputes/${disputeId}/resolve`,
    payload
  )
  return res.data
}

export async function getAuditHealth(): Promise<APIResponse<any>> {
  const res = await apiClient.get<APIResponse<any>>('/audits/health')
  return res.data
}

export async function getAuditDashboardQueues(): Promise<APIResponse<import('../types').AuditQueueGroup>> {
  const res = await apiClient.get<APIResponse<import('../types').AuditQueueGroup>>('/audits/dashboard-queues')
  return res.data
}

export async function getAuditLogs(params?: { limit?: number; offset?: number }): Promise<APIResponse<import('../types').ActivityLogItem[]>> {
  const res = await apiClient.get<APIResponse<import('../types').ActivityLogItem[]>>('/audits/logs', { params })
  return res.data
}

export async function getAuditIntegrityFlags(
  auditId: string
): Promise<APIResponse<import('../types').ProjectIntegrityReport>> {
  const res = await apiClient.get<APIResponse<import('../types').ProjectIntegrityReport>>(
    `/audits/${auditId}/integrity-flags`
  )
  return res.data
}

export async function getProjectIntegrityFlags(
  projectId: string
): Promise<APIResponse<import('../types').ProjectIntegrityReport>> {
  const res = await apiClient.get<APIResponse<import('../types').ProjectIntegrityReport>>(
    `/risk/projects/${projectId}/integrity-flags`
  )
  return res.data
}
