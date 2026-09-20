import axios from 'axios'
import { message } from 'antd'
import { getAccessToken } from '../utils/token'
import { useAuthStore } from '../store/authStore'

export const request = axios.create({
  // 默认走同源 /api（vite dev proxy -> localhost:8002），局域网访问无需改地址；
  // 也可用 VITE_API_BASE_URL 覆盖为完整后端地址。
  baseURL: import.meta.env.VITE_API_BASE_URL ?? '/api/v1',
  timeout: 15_000,
})

request.interceptors.request.use((config) => {
  config.headers.set('X-Client', 'life-health-desktop')
  const token = getAccessToken()
  if (token) config.headers.set('Authorization', `Bearer ${token}`)
  return config
})

request.interceptors.response.use(
  (response) => response,
  (error) => {
    const detail = error.response?.data?.detail
    if (error.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.assign('/login')
    } else if (error.response?.status === 403 && detail === '该账号已被禁用，请联系企业管理员') {
      useAuthStore.getState().logout()
      window.location.assign('/login')
      message.error('当前账号已被管理员禁用，请联系企业管理员')
    }
    return Promise.reject(error)
  },
)
