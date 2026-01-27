import axios from 'axios'
import type { AxiosInstance, AxiosRequestConfig } from 'axios'

const API_BASE_URL = (import.meta as any).env?.VITE_API_URL || 'http://localhost:8001'

class ApiClient {
  private client: AxiosInstance

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      timeout: 10000,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    // Error interceptor
    this.client.interceptors.response.use(
      response => response,
      error => {
        // Don't redirect on 401 for trading authentication endpoints
        // Let the component handle the error instead
        if (error.response?.status === 401) {
          const url = error.config?.url || ''
          // Only redirect for non-trading endpoints
          if (!url.includes('/trading/')) {
            console.warn('Unauthorized request, consider redirecting to login')
            // window.location.href = '/login'  // Disabled to prevent OTP flow crashes
          }
        }
        return Promise.reject(error)
      }
    )
  }

  async get<T>(url: string, config?: AxiosRequestConfig) {
    return this.client.get<T>(url, config)
  }

  async post<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.client.post<T>(url, data, config)
  }

  async put<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.client.put<T>(url, data, config)
  }

  async patch<T>(url: string, data?: any, config?: AxiosRequestConfig) {
    return this.client.patch<T>(url, data, config)
  }

  async delete<T>(url: string, config?: AxiosRequestConfig) {
    return this.client.delete<T>(url, config)
  }
}

export const apiClient = new ApiClient(API_BASE_URL)

export default apiClient
