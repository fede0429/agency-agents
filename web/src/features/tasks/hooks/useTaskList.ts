// src/features/tasks/hooks/useTaskList.ts
import { useState, useCallback, useEffect } from 'react';
import type { PageState, TaskListViewModel, TaskListDTO } from '../types';
import { transformTaskDtoList } from '../transform';
import { fetchApi } from '../../../lib/api';

export function useTaskList(moduleType: string) {
  const [state, setState] = useState<PageState<TaskListViewModel[]>>({ status: 'loading' });

  const fetchTasks = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const res = await fetchApi<TaskListDTO[]>(`/tasks?module_type=${moduleType}`);
      if (!res.success) {
        throw new Error(res.error?.message || '获取任务列表失败');
      }
      
      const vms = (res.data || []).map(transformTaskDtoList);
      
      setState(vms.length === 0 
        ? { status: 'empty' } 
        : { status: 'success', data: vms }
      );
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : '未知错误';
      setState({ status: 'error', message: msg, retryable: true });
    }
  }, [moduleType]);

  useEffect(() => {
    fetchTasks();
  }, [fetchTasks]);

  return { state, actions: { refresh: fetchTasks } };
}
