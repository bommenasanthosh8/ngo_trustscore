/**
 * Donations & Direct NGO Payment API client.
 */
import apiClient from './client'
import type { APIResponse } from '@/types'

export type PaymentMethod = 'UPI' | 'CARD' | 'NET_BANKING' | 'RAZORPAY_GATEWAY'

export interface CreateDonationPayload {
  ngo_id: string
  project_id?: string
  amount: number
  currency?: string
  payment_method: PaymentMethod
  donor_name?: string
  donor_email?: string
  donor_notes?: string
}

export interface DonationRecord {
  id: string
  donor_id: string | null
  donor_name: string
  donor_email: string
  ngo_id: string
  ngo_name: string
  ngo_registration_number?: string | null
  project_id?: string | null
  project_code?: string | null
  project_title?: string | null
  amount: number
  currency: string
  payment_method: PaymentMethod
  transaction_id: string
  payment_status: 'SUCCESS' | 'PENDING' | 'FAILED'
  receipt_number: string
  tax_exemption_eligible: boolean
  donor_notes?: string | null
  created_at: string
  completed_at?: string | null
}

export interface MyDonationsResponse {
  items: DonationRecord[]
  total_donated: number
  total_donations_count: number
  supported_ngos_count: number
}

export interface DonationStatsResponse {
  total_funds_disbursed_inr: number
  total_direct_donations: number
  tax_exemption_standard: string
}

export const donationsApi = {
  create: (payload: CreateDonationPayload) =>
    apiClient.post<APIResponse<DonationRecord>>('/donations', payload),

  getMyDonations: () =>
    apiClient.get<APIResponse<MyDonationsResponse>>('/donations/my-donations'),

  getStats: () =>
    apiClient.get<APIResponse<DonationStatsResponse>>('/donations/stats'),

  getById: (id: string) =>
    apiClient.get<APIResponse<DonationRecord>>(`/donations/${id}`),
}
