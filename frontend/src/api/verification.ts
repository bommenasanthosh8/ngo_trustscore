import apiClient from './client'
import { APIResponse, VerificationReport } from '../types'

export async function triggerProjectVerification(
  projectId: string,
): Promise<APIResponse<VerificationReport>> {
  const res = await apiClient.post<APIResponse<VerificationReport>>(
    `/projects/${projectId}/verify`
  )
  return res.data
}

export async function getProjectVerification(
  projectId: string,
): Promise<APIResponse<VerificationReport>> {
  const res = await apiClient.get<APIResponse<VerificationReport>>(
    `/projects/${projectId}/verification`
  )
  return res.data
}

export async function verifyEvidence(
  evidenceId: string,
): Promise<APIResponse<VerificationReport>> {
  const res = await apiClient.post<APIResponse<VerificationReport>>(
    `/verification/evidence/${evidenceId}/verify`
  )
  return res.data
}

export async function getVerificationHealth(): Promise<APIResponse<any>> {
  const res = await apiClient.get<APIResponse<any>>('/verification/health')
  return res.data
}
