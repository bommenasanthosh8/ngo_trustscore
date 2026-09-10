import apiClient from './client'
import { APIResponse, RiskAssessmentResponse } from '../types'

export async function getProjectRisk(
  projectId: string,
): Promise<APIResponse<RiskAssessmentResponse>> {
  const res = await apiClient.get<APIResponse<RiskAssessmentResponse>>(
    `/projects/${projectId}/risk`
  )
  return res.data
}

export async function evaluateProjectRisk(
  projectId: string,
): Promise<APIResponse<RiskAssessmentResponse>> {
  const res = await apiClient.post<APIResponse<RiskAssessmentResponse>>(
    `/risk/projects/${projectId}/evaluate`
  )
  return res.data
}

export async function getRiskHealth(): Promise<APIResponse<any>> {
  const res = await apiClient.get<APIResponse<any>>('/risk/health')
  return res.data
}
