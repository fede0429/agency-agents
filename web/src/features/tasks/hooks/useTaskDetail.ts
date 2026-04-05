// src/features/tasks/hooks/useTaskDetail.ts
import { useState, useCallback, useEffect } from 'react';
import type { PageState, TaskDetailViewModel, TaskDetailDTO } from '../types';
import { transformTaskDetailDto } from '../transform';
import { fetchApi } from '../../../lib/api';

const PENDING_STATUSES = ['queued', 'analyzing', 'scripting', 'storyboarding', 'stitching', 'publishing'];
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1';

export function useTaskDetail(taskId: string) {
  const [state, setState] = useState<PageState<TaskDetailViewModel>>({ status: 'loading' });

  // Initial fetch to get the base state
  const fetchInitialDetail = useCallback(async (): Promise<boolean> => {
    try {
      const res = await fetchApi<TaskDetailDTO>(`/tasks/${taskId}`);
      if (!res.success) throw new Error(res.error?.message || '获取任务详情失败');
      
      const vm = transformTaskDetailDto(res.data!);
      setState({ status: 'success', data: vm });
      
      return PENDING_STATUSES.includes(vm.status);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知连通性问题';
      setState(prev => prev.status === 'success' ? prev : { status: 'error', message: msg, retryable: true });
      return false; // Stop trying
    }
  }, [taskId]);

  useEffect(() => {
    let sse: EventSource | null = null;
    let isSubscribed = true;

    const initSequence = async () => {
      setState({ status: 'loading' });
      const needsStream = await fetchInitialDetail();
      
      if (needsStream && isSubscribed) {
        // Start EventSource to listen to continuous updates
        const sseUrl = `${API_BASE_URL}/tasks/${taskId}/stream`;
        sse = new EventSource(sseUrl);

        sse.onmessage = (event) => {
          if (!isSubscribed) return;
          try {
            const payload = JSON.parse(event.data);
            
            setState(prev => {
              if (prev.status !== 'success') return prev;
              
              const currentData = { ...prev.data, timeline: [...prev.data.timeline] };
              let hasChanges = false;

              if (payload.type === 'timeline') {
                // ...
                const newStep = payload.data;
                const stepMap: Record<string, string> = {
                  analyze: '素材提取',
                  scripting: 'AI文案创作',
                  storyboarding: '分镜生成',
                  stitching: '视频拼接',
                  publishing: '多端发布',
                  grid_merging: '基线拼贴',
                  assets: '资产解析',
                  segments: '片段划分',
                  shots: '镜头编排',
                  packaging: '结构封装',
                  download_video: '视频下载',
                  narration_pipeline: 'AI解说生成'
                };

                const existingIdx = currentData.timeline.findIndex(t => t.step === newStep.step);
                const mappedStep = {
                  step: newStep.step,
                  stepLabel: stepMap[newStep.step] || newStep.step,
                  status: newStep.status,
                  tookMs: newStep.took_ms || null,
                  error: newStep.error || null
                };

                if (existingIdx !== -1) {
                  const existingStep = currentData.timeline[existingIdx];
                  if (newStep.message) {
                    mappedStep.stepLabel = `${existingStep.stepLabel.split(' - ')[0]} - ${newStep.message}`;
                  } else {
                     // Keep the existing label if no new message is provided but preserve structure
                     mappedStep.stepLabel = existingStep.stepLabel;
                  }
                  currentData.timeline[existingIdx] = mappedStep;
                } else {
                  if (newStep.message) {
                    mappedStep.stepLabel = `${mappedStep.stepLabel} - ${newStep.message}`;
                  }
                  currentData.timeline.push(mappedStep);
                }
                hasChanges = true;
              } else if (payload.type === 'state') {
                const statusMap: Record<string, { label: string, color: string }> = {
                  queued: { label: '排队中', color: 'gray' },
                  analyzing: { label: '素材分析', color: 'blue' },
                  scripting: { label: '剧本创作', color: 'indigo' },
                  storyboarding: { label: '分镜生成', color: 'cyan' },
                  stitching: { label: '视频合成', color: 'purple' },
                  publishing: { label: '平台发布', color: 'yellow' },
                  success: { label: '已发布', color: 'green' },
                  failed: { label: '生成失败', color: 'red' },
                };
                
                if (payload.status) {
                  currentData.status = payload.status;
                  const sInfo = statusMap[payload.status] || statusMap['queued'];
                  currentData.statusLabel = sInfo.label;
                  currentData.statusColor = sInfo.color;
                  hasChanges = true;
                }
                // We ignore strict progress% tracking right now, driving entirely by timeline
              }

              return hasChanges ? { ...prev, data: currentData } : prev;
            });
          } catch (e) {
             console.error('SSE Payload Parse Error', e);
          }
        };

        sse.onerror = (e) => {
          console.error('SSE Error', e);
          // If the connection drops or the server closes it (e.g. task success/fail),
          // handle fallback: rely on close event or manual closure.
          // Re-fetching full details guarantees we get `artifacts` (e.g. video URL) once completed stream dies.
          if (sse) sse.close();
          fetchInitialDetail(); // do one final fetch to sync DB artifacts (video_url etc.) when connection fails/closes
        };
        
        sse.addEventListener('close', () => {
             if (sse) sse.close();
             fetchInitialDetail(); // Fetch final state including video artifacts
        });
      }
    };

    initSequence();

    return () => {
      isSubscribed = false;
      if (sse) {
        sse.close();
      }
    };
  }, [fetchInitialDetail, taskId]);

  return { state, refetch: fetchInitialDetail };
}
