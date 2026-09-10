import apiClient from './client'
import type {
  APIResponse,
  EvidenceListResponse,
  EvidenceTimelineResponse,
  FinancialConsistencyReport,
  NGOPublicSummary,
  NGOResponse,
  ProjectDetail,
  ProjectVerificationSummary,
  PublicMapPoint,
  PublicPlatformStats,
} from '../types'

export async function getPublicStats(): Promise<APIResponse<PublicPlatformStats>> {
  const res = await apiClient.get<APIResponse<PublicPlatformStats>>('/public/stats')
  return res.data
}

export async function getPublicMapPoints(params?: {
  category?: string
  status?: string
}): Promise<APIResponse<PublicMapPoint[]>> {
  const res = await apiClient.get<APIResponse<PublicMapPoint[]>>('/public/projects/map', {
    params,
  })
  return res.data
}

export async function getPublicVerificationSummary(
  projectId: string
): Promise<APIResponse<ProjectVerificationSummary>> {
  const res = await apiClient.get<APIResponse<ProjectVerificationSummary>>(
    `/public/projects/${projectId}/verification-summary`
  )
  return res.data
}

export async function searchPublicNGOs(params?: {
  search?: string
  category?: string
  location?: string
  status?: string
  skip?: number
  limit?: number
}): Promise<APIResponse<NGOPublicSummary[]>> {
  const res = await apiClient.get<APIResponse<NGOPublicSummary[]>>('/ngos', { params })
  return res.data
}

export async function getPublicNGOProfile(ngoId: string): Promise<APIResponse<NGOResponse>> {
  const res = await apiClient.get<APIResponse<NGOResponse>>(`/ngos/${ngoId}`)
  return res.data
}

export async function getPublicProjects(params?: {
  category?: string
  status?: string
  search?: string
  ngo_id?: string
  skip?: number
  limit?: number
}): Promise<APIResponse<ProjectDetail[]>> {
  const res = await apiClient.get<APIResponse<ProjectDetail[]>>('/projects', { params })
  return res.data
}

export async function getPublicProjectDetail(
  projectId: string
): Promise<APIResponse<ProjectDetail>> {
  const res = await apiClient.get<APIResponse<ProjectDetail>>(`/projects/${projectId}`)
  return res.data
}

export async function getPublicProjectEvidence(
  projectId: string
): Promise<APIResponse<EvidenceListResponse>> {
  const res = await apiClient.get<APIResponse<EvidenceListResponse>>(
    `/projects/${projectId}/evidence`
  )
  return res.data
}

export async function getPublicProjectTimeline(
  projectId: string
): Promise<APIResponse<EvidenceTimelineResponse>> {
  const res = await apiClient.get<APIResponse<EvidenceTimelineResponse>>(
    `/projects/${projectId}/evidence/timeline`
  )
  return res.data
}

export async function getPublicFinancialConsistency(
  projectId: string
): Promise<APIResponse<FinancialConsistencyReport>> {
  const res = await apiClient.get<APIResponse<FinancialConsistencyReport>>(
    `/projects/${projectId}/financial-evidence/consistency`
  )
  return res.data
}
