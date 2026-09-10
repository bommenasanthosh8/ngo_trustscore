import apiClient from './client'
import {
  ActivityLogItem,
  AdminDisputeItem,
  APIResponse,
  AuditConfig,
  NGOResponse,
  ResolveDisputeRequest,
  SystemStats,
} from '../types'

export interface LogFilterParams {
  action?: string
  actor_role?: string
  resource_type?: string
  limit?: number
  offset?: number
}

export interface AuditConfigUpdatePayload {
  high_project_value_threshold?: number
  audit_random_sample_rate?: number
  high_risk_threshold?: number
  auto_audit_enabled?: boolean
}

export const adminApi = {
  getPendingNgos: () =>
    apiClient.get<APIResponse<NGOResponse[]>>('/admin/ngos/pending'),

  verifyNgo: (id: string) =>
    apiClient.post<APIResponse<NGOResponse>>(`/admin/ngos/${id}/verify`),

  rejectNgo: (id: string, reason?: string) =>
    apiClient.post<APIResponse<NGOResponse>>(`/admin/ngos/${id}/reject`, { reason }),

  getAuditConfig: () =>
    apiClient.get<APIResponse<AuditConfig>>('/admin/audit-config'),

  updateAuditConfig: (payload: AuditConfigUpdatePayload) =>
    apiClient.put<APIResponse<AuditConfig>>('/admin/audit-config', payload),

  getDisputes: (status?: string) =>
    apiClient.get<APIResponse<AdminDisputeItem[]>>('/admin/disputes', {
      params: status ? { status } : undefined,
    }),

  resolveDispute: (id: string, payload: ResolveDisputeRequest) =>
    apiClient.post<APIResponse<any>>(`/admin/disputes/${id}/resolve`, payload),

  getLogs: (params?: LogFilterParams) =>
    apiClient.get<APIResponse<ActivityLogItem[]>>('/admin/logs', { params }),

  getStats: () =>
    apiClient.get<APIResponse<SystemStats>>('/admin/stats'),
}

export default adminApi
