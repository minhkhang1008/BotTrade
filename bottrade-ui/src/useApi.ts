import { useCallback } from 'react'
import { apiClient } from '../services/api'
import { AxiosError } from 'axios'

interface UseApiReturn {
  get: <T = any>(url: string) => Promise<any>
  post: <T = any>(url: string, data?: any) => Promise<any>
  put: <T = any>(url: string, data?: any) => Promise<any>
  delete: <T = any>(url: string) => Promise<any>
  loading: boolean
  error: string | null
}

export const useApi = () => {
  const handleError = useCallback((error: AxiosError) => {
    const message = error.response?.data?.detail || error.message || 'An error occurred'
    return message
  }, [])

  const get = useCallback(async (url: string) => {
    try {
      return await apiClient.get(url)
    } catch (error) {
      throw new Error(handleError(error as AxiosError))
    }
  }, [handleError])

  const post = useCallback(async (url: string, data: any) => {
    try {
      return await apiClient.post(url, data)
    } catch (error) {
      throw new Error(handleError(error as AxiosError))
    }
  }, [handleError])

  const put = useCallback(async (url: string, data: any) => {
    try {
      return await apiClient.put(url, data)
    } catch (error) {
      throw new Error(handleError(error as AxiosError))
    }
  }, [handleError])

  const deleteReq = useCallback(async (url: string) => {
    try {
      return await apiClient.delete(url)
    } catch (error) {
      throw new Error(handleError(error as AxiosError))
    }
  }, [handleError])

  return { get, post, put, delete: deleteReq, loading: false, error: null }
}

export default useApi
