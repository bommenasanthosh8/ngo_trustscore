/**
 * Auth API calls — login, register, refresh, get current user.
 */
import apiClient from './client'
import type {
  APIResponse,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserProfile,
} from '@/types'

export const authApi = {
  login: (body: LoginRequest) =>
    apiClient.post<APIResponse<TokenResponse>>('/auth/login', body),

  register: (body: RegisterRequest) =>
    apiClient.post<APIResponse<UserProfile>>('/auth/register', body),

  refresh: (refreshToken: string) =>
    apiClient.post<APIResponse<TokenResponse>>('/auth/refresh', {
      refresh_token: refreshToken,
    }),

  me: () => apiClient.get<APIResponse<UserProfile>>('/auth/me'),

  logout: () => apiClient.post<APIResponse<{ message: string }>>('/auth/logout'),

  loginHistory: () => apiClient.get<APIResponse<Array<{
    id: string
    action: string
    actor_role: string | null
    ip_address: string | null
    success: boolean
    created_at: string
    detail: any
  }>>>('/auth/login-history'),
}
