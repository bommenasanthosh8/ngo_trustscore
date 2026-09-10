/**
 * Projects API calls — browsing, creation, detail view, status transitions, and geospatial search.
 */
import apiClient from './client'
import type {
  APIResponse,
  CreateProjectRequest,
  LocationSearchResult,
  ProjectDetail,
  ProjectStatus,
  ProjectType,
  UpdateProjectRequest,
} from '@/types'

export interface ProjectListParams {
  category?: ProjectType
  status?: ProjectStatus
  search?: string
  ngo_id?: string
  skip?: number
  limit?: number
}

export const projectsApi = {
  list: (params?: ProjectListParams) =>
    apiClient.get<APIResponse<ProjectDetail[]>>('/projects', { params }),

  getById: (idOrCode: string) =>
    apiClient.get<APIResponse<ProjectDetail>>(`/projects/${idOrCode}`),

  create: (body: CreateProjectRequest) =>
    apiClient.post<APIResponse<ProjectDetail>>('/projects', body),

  update: (idOrCode: string, body: UpdateProjectRequest) =>
    apiClient.patch<APIResponse<ProjectDetail>>(`/projects/${idOrCode}`, body),

  searchLocations: (q: string) =>
    apiClient.get<APIResponse<LocationSearchResult[]>>('/projects/locations/search', {
      params: { q },
    }),

  getRisk: (idOrCode: string) =>
    apiClient.get<APIResponse<any>>(`/projects/${idOrCode}/risk`),

  getVerification: (idOrCode: string) =>
    apiClient.get<APIResponse<any>>(`/projects/${idOrCode}/verification`),

  triggerVerification: (idOrCode: string) =>
    apiClient.post<APIResponse<any>>(`/projects/${idOrCode}/verify`),

  getAudits: (idOrCode: string) =>
    apiClient.get<APIResponse<any[]>>(`/projects/${idOrCode}/audits`),

  getDisputes: (idOrCode: string) =>
    apiClient.get<APIResponse<any[]>>(`/projects/${idOrCode}/disputes`),

  raiseDispute: (idOrCode: string, reason: string) =>
    apiClient.post<APIResponse<any>>(`/projects/${idOrCode}/dispute`, { reason }),
}

