/**
 * NGO API calls — onboarding, profile management, and admin verification.
 */
import apiClient from './client'
import type {
  APIResponse,
  CreateNGORequest,
  NGOResponse,
  NGOVerificationStatus,
  UpdateNGORequest,
} from '@/types'

export const ngoApi = {
  // ── NGO operations ────────────────────────────────────────────────────────
  create: (body: CreateNGORequest) =>
    apiClient.post<APIResponse<NGOResponse>>('/ngos', body),

  getById: (id: string) =>
    apiClient.get<APIResponse<NGOResponse>>(`/ngos/${id}`),

  update: (id: string, body: UpdateNGORequest) =>
    apiClient.patch<APIResponse<NGOResponse>>(`/ngos/${id}`, body),

  list: (status?: NGOVerificationStatus) =>
    apiClient.get<APIResponse<NGOResponse[]>>('/ngos', {
      params: status ? { status } : undefined,
    }),

  // ── Admin verification operations ─────────────────────────────────────────
  getPending: () =>
    apiClient.get<APIResponse<NGOResponse[]>>('/admin/ngos/pending'),

  verify: (id: string) =>
    apiClient.post<APIResponse<NGOResponse>>(`/admin/ngos/${id}/verify`),

  reject: (id: string, reason?: string) =>
    apiClient.post<APIResponse<NGOResponse>>(`/admin/ngos/${id}/reject`, { reason }),
}
