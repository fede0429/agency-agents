// src/features/tasks/types.ts

// --- Data Transfer Objects (DTOs) from Backend ---
export interface TaskListDTO {
  task_id: string;
  created_at: string;
  target_url: string;
  status: 'queued' | 'analyzing' | 'scripting' | 'storyboarding' | 'stitching' | 'publishing' | 'success' | 'failed';
  progress_percent: number | null;
  publish_platforms: string[];
  thumbnail_url: string | null;
  error_message: string | null;
}

export interface TaskDetailDTO {
  task_id: string;
  status: 'queued' | 'analyzing' | 'scripting' | 'storyboarding' | 'stitching' | 'publishing' | 'success' | 'failed';
  created_at: string;
  source_metadata: {
    url: string;
    title?: string;
  } | null;
  artifacts: {
    script: string | null;
    storyboard: any | null;
    video_url: string | null;
  } | null;
  timeline: {
    step: string;
    status: 'pending' | 'processing' | 'success' | 'failed';
    took_ms: number | null;
    error: string | null;
  }[];
}

// --- Generic API Response ---
export interface ErrorDetail {
  code: string;
  message: string;
  retryable: boolean;
  field?: string;
}

export interface ApiResponse<T> {
  success: boolean;
  data?: T;
  error?: ErrorDetail;
  meta?: {
    total?: number;
    page?: number;
    pageSize?: number;
    tookMs?: number;
  };
}

// --- ViewModels for Frontend Rendering ---
export interface TaskListViewModel {
  id: string;
  createdAtFormatted: string;
  status: 'queued' | 'analyzing' | 'scripting' | 'storyboarding' | 'stitching' | 'publishing' | 'success' | 'failed';
  statusLabel: string;
  statusColor: string;
  progress: number;
  platforms: string[];
  thumbnail: string;
}

export interface TaskDetailViewModel {
  id: string;
  status: 'queued' | 'analyzing' | 'scripting' | 'storyboarding' | 'stitching' | 'publishing' | 'success' | 'failed';
  statusLabel: string;
  statusColor: string;
  createdAtFormatted: string;
  sourceUrl: string;
  title: string;
  script: string | null;
  videoUrl: string | null;
  timeline: {
    step: string;
    stepLabel: string;
    status: 'pending' | 'processing' | 'success' | 'failed';
    tookMs: number | null;
    error: string | null;
  }[];
}

// --- UI State Types ---
export type PageState<T> =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'success'; data: T }
  | { status: 'empty' }
  | { status: 'error'; message: string; retryable: boolean };
