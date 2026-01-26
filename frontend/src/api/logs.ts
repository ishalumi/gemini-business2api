import apiClient from './client'
import type { AdminLogsResponse } from '@/types/api'

export const logsApi = {
  // 获取日志
  list: (params?: { limit?: number; level?: string; search?: string }) =>
    apiClient.get<never, AdminLogsResponse>('/admin/log', { params }),

  // 清空日志
  clear: () =>
    apiClient.delete('/admin/log?confirm=yes'),

  // 获取安全日志
  listSecurity: (params?: { limit?: number; level?: string; search?: string }) =>
    apiClient.get<never, AdminLogsResponse>('/admin/security/log', { params }),

  // 清空安全日志
  clearSecurity: () =>
    apiClient.delete('/admin/security/log?confirm=yes'),
}
