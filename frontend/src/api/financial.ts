/**
 * Financial Evidence API calls — upload, listing, and financial consistency evaluation.
 */
import apiClient from './client'
import type {
  APIResponse,
  FinancialConsistencyReport,
  FinancialDocumentType,
  FinancialEvidence,
  ProjectFinancialEvidenceListResponse,
} from '@/types'

export interface UploadFinancialPayload {
  file: File
  claimed_amount: number
  document_type: FinancialDocumentType
  currency?: string
  vendor_name?: string
  invoice_number?: string
  document_date?: string
  description?: string
}

export const financialApi = {
  /**
   * Upload a financial document (invoice, bill, receipt) with expenditure claim.
   */
  upload: (projectId: string, payload: UploadFinancialPayload) => {
    const formData = new FormData()
    formData.append('file', payload.file)
    formData.append('claimed_amount', String(payload.claimed_amount))
    formData.append('document_type', payload.document_type)

    if (payload.currency) {
      formData.append('currency', payload.currency)
    }
    if (payload.vendor_name) {
      formData.append('vendor_name', payload.vendor_name)
    }
    if (payload.invoice_number) {
      formData.append('invoice_number', payload.invoice_number)
    }
    if (payload.document_date) {
      formData.append('document_date', payload.document_date)
    }
    if (payload.description) {
      formData.append('description', payload.description)
    }

    return apiClient.post<APIResponse<FinancialEvidence>>(
      `/projects/${projectId}/financial-evidence`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      }
    )
  },

  /**
   * List all financial evidence records for a project along with consistency report.
   */
  list: (projectId: string) =>
    apiClient.get<APIResponse<ProjectFinancialEvidenceListResponse>>(
      `/projects/${projectId}/financial-evidence`
    ),

  /**
   * Get standalone financial consistency report for a project.
   */
  getConsistency: (projectId: string) =>
    apiClient.get<APIResponse<FinancialConsistencyReport>>(
      `/projects/${projectId}/financial-evidence/consistency`
    ),
}
