import apiClient from './client'
import {
  APIResponse,
  NGOScoreSnapshotResponse,
  NGOTransparencyScoreResponse,
  ProjectScoreResponse,
} from '../types'

export async function getProjectScore(
  projectId: string
): Promise<APIResponse<ProjectScoreResponse>> {
  const res = await apiClient.get<APIResponse<ProjectScoreResponse>>(
    `/projects/${projectId}/score`
  )
  return res.data
}

export async function recalculateProjectScore(
  projectId: string
): Promise<APIResponse<ProjectScoreResponse>> {
  const res = await apiClient.post<APIResponse<ProjectScoreResponse>>(
    `/scores/projects/${projectId}/recalculate`
  )
  return res.data
}

export async function getNGOScore(
  ngoId: string
): Promise<APIResponse<NGOTransparencyScoreResponse>> {
  const res = await apiClient.get<APIResponse<NGOTransparencyScoreResponse>>(
    `/ngos/${ngoId}/score`
  )
  return res.data
}

export async function getNGOScoreHistory(
  ngoId: string
): Promise<APIResponse<NGOScoreSnapshotResponse[]>> {
  const res = await apiClient.get<APIResponse<NGOScoreSnapshotResponse[]>>(
    `/ngos/${ngoId}/score/history`
  )
  return res.data
}

export async function getScoreHealth(): Promise<APIResponse<any>> {
  const res = await apiClient.get<APIResponse<any>>('/scores/health')
  return res.data
}

