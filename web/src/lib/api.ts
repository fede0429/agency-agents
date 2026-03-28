// src/lib/api.ts
import type { ApiResponse } from '../features/tasks/types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export async function fetchApi<T>(endpoint: string, options?: RequestInit): Promise<ApiResponse<T>> {
  try {
    const res = await fetch(`${API_BASE_URL}${endpoint}`, {
      ...options,
      headers: {
        'Content-Type': 'application/json',
        ...options?.headers,
      },
    });
    
    if (!res.ok) {
      throw new Error(`请求失败: ${res.status} ${res.statusText}`);
    }

    const data = await res.json();
    return data;
  } catch (error: unknown) {
    const errorMessage = error instanceof Error ? error.message : '未知网络连接失败';
    return {
      success: false,
      error: {
        code: 'NETWORK_ERROR',
        message: errorMessage,
        retryable: true
      }
    };
  }
}
