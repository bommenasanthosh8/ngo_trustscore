/**
 * Evidence API calls — upload, listing, timeline retrieval, and file streaming.
 */
import apiClient from './client'
import type {
  APIResponse,
  Evidence,
  EvidenceTimelineResponse,
  EvidenceType,
} from '@/types'

export interface UploadEvidencePayload {
  file: File
  title: string
  evidence_type: EvidenceType
  description?: string
  captured_at?: string
  latitude?: number
  longitude?: number
  gps_accuracy?: number
  supersedes_id?: string
  metadata_summary?: Record<string, any>
}

export const evidenceApi = {
  /**
   * Upload an immutable evidence item bound to a specific project.
   */
  upload: (projectId: string, payload: UploadEvidencePayload) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('title', payload.title)
    formData.append('evidence_type', payload.evidence_type)

    if (payload.description) {
      formData.append('description', payload.description)
    }
    if (payload.captured_at) {
      formData.append('captured_at', payload.captured_at)
    }
    if (payload.latitude !== undefined && payload.latitude !== null) {
      formData.append('latitude', String(payload.latitude))
    }
    if (payload.longitude !== undefined && payload.longitude !== null) {
      formData.append('longitude', String(payload.longitude))
    }
    if (payload.gps_accuracy !== undefined && payload.gps_accuracy !== null) {
      formData.append('gps_accuracy', String(payload.gps_accuracy))
    }
    if (payload.supersedes_id) {
      formData.append('supersedes_id', payload.supersedes_id)
    }
    if (payload.metadata_summary) {
      formData.append('metadata_summary', JSON.stringify(payload.metadata_summary))
    }

    return apiClient.post<APIResponse<Evidence>>(`/projects/${projectId}/evidence`, formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    })
  },

  /**
   * List all evidence records for a project, optionally filtered by evidence type.
   */
  listByProject: (projectId: string, evidenceType?: EvidenceType) =>
    apiClient.get<APIResponse<{ items: Evidence[]; total: number; project_id: string }>>(
      `/projects/${projectId}/evidence`,
      {
        params: evidenceType ? { evidence_type: evidenceType } : undefined,
      }
    ),

  /**
   * Get chronological milestone timeline for a project.
   */
  getTimeline: (projectId: string) =>
    apiClient.get<APIResponse<EvidenceTimelineResponse>>(`/projects/${projectId}/evidence/timeline`),

  /**
   * Get single evidence detail.
   */
  getById: (evidenceId: string) =>
    apiClient.get<APIResponse<Evidence>>(`/evidence/${evidenceId}`),

  /**
   * List all evidence submitted across organization projects.
   */
  listAll: (params?: { project_id?: string; evidence_type?: EvidenceType; limit?: number; offset?: number }) =>
    apiClient.get<APIResponse<any[]>>('/evidence', { params }),

  /**
   * Download/stream protected evidence file.
   */
  downloadFile: (evidenceId: string) =>
    apiClient.get(`/evidence/${evidenceId}/file`, {
      responseType: 'blob',
    }),
}
