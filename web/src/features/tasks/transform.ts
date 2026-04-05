// src/features/tasks/transform.ts
import type { TaskListDTO, TaskListViewModel, TaskDetailDTO, TaskDetailViewModel } from './types';

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

export function transformTaskDtoList(dto: TaskListDTO): TaskListViewModel {
  const statusInfo = statusMap[dto.status] ?? statusMap['queued'];
  
  return {
    id: dto.task_id,
    createdAtFormatted: new Date(dto.created_at).toLocaleString('zh-CN'),
    status: dto.status,
    statusLabel: statusInfo.label,
    statusColor: statusInfo.color,
    progress: dto.progress_percent ?? 0,
    platforms: dto.publish_platforms.map(p => p.toUpperCase()),
    thumbnail: dto.thumbnail_url ?? '',
  };
}

export function transformTaskDetailDto(dto: TaskDetailDTO): TaskDetailViewModel {
  const statusInfo = statusMap[dto.status] ?? statusMap['queued'];

  const timelineStepsMap: Record<string, string> = {
    analyze: '素材提取',
    scripting: 'AI文案创作',
    storyboarding: '分镜生成',
    stitching: '视频拼接',
    publishing: '多端发布',
    download_video: '视频下载',
    narration_pipeline: 'AI解说生成'
  }

  const mergedTimeline: any[] = [];
  dto.timeline.forEach(t => {
    const stepLabelBase = timelineStepsMap[t.step] || t.step;
    // @ts-ignore
    const stepLabel = t.message ? `${stepLabelBase} - ${t.message}` : stepLabelBase;
    const existingIdx = mergedTimeline.findIndex(item => item.step === t.step);
    if (existingIdx !== -1) {
      mergedTimeline[existingIdx] = { ...mergedTimeline[existingIdx], ...t, stepLabel };
    } else {
      mergedTimeline.push({ ...t, stepLabel });
    }
  });

  return {
    id: dto.task_id,
    status: dto.status,
    statusLabel: statusInfo.label,
    statusColor: statusInfo.color,
    createdAtFormatted: new Date(dto.created_at).toLocaleString('zh-CN'),
    sourceUrl: dto.source_metadata?.url ?? '',
    title: dto.source_metadata?.title ?? '未知任务',
    script: dto.artifacts?.script ?? null,
    videoUrl: dto.artifacts?.video_url ?? null,
    timeline: mergedTimeline
  };
}
