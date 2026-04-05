import { useState } from 'react';
import { Play, Plus, Video } from 'lucide-react';
import { useTaskList } from '../features/tasks/hooks/useTaskList';
import { Skeleton, ErrorState, EmptyState } from '../components/ui/States';
import type { TaskListViewModel } from '../features/tasks/types';
import { Link } from 'react-router-dom';
import { TaskCreateDialog } from '../features/tasks/components/TaskCreateDialog';

export function TaskListPage() {
  const [activeTab, setActiveTab] = useState<'ugc' | 'anime' | 'short_video' | 'narration'>('short_video');
  const { state, actions } = useTaskList(activeTab);
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  return (
    <div className="max-w-6xl mx-auto py-8 px-6">
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight mb-2">编排任务大厅</h1>
          <p className="text-foreground/60">自动化分析竞品并生成带有语音、分镜的完整短视频</p>
        </div>
        <button 
          onClick={() => setIsDialogOpen(true)}
          className="bg-primary hover:bg-primary-hover text-white px-5 py-2.5 rounded-lg font-medium flex items-center gap-2 transition-all shadow-lg shadow-primary/20 hover:shadow-primary/40 hover:-translate-y-0.5 active:translate-y-0"
        >
          <Plus className="w-5 h-5" />
          {activeTab === 'ugc' ? '新建带货视频' : activeTab === 'anime' ? '新建动漫剧' : activeTab === 'narration' ? '新建旁白视频' : '新建短视频'}
        </button>
      </div>

      <div className="flex gap-2 mb-8 glass-panel p-1.5 rounded-xl w-fit overflow-x-auto max-w-full relative z-10">
        {[
          { id: 'ugc', label: '🛒 UGC带货视频' },
          { id: 'anime', label: '🎌 动漫剧集' },
          { id: 'short_video', label: '📱 综合短视频' },
          { id: 'narration', label: '🎙️ AI解说旁白' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`px-5 py-2 rounded-lg text-sm font-medium transition-all ${
              activeTab === tab.id 
                ? 'bg-primary/20 border border-primary/30 text-primary shadow-inner' 
                : 'text-foreground/50 hover:text-foreground hover:bg-white/5 border border-transparent'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div className="min-h-[60vh]">
        {state.status === 'loading' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {Array.from({ length: 6 }).map((_, i) => (
              <Skeleton key={i} className="h-64 rounded-xl" />
            ))}
          </div>
        )}

        {state.status === 'error' && (
          <ErrorState message={state.message} action={{ label: '重试获取列表', onClick: actions.refresh }} />
        )}

        {state.status === 'empty' && (
          <EmptyState 
            icon={<Video className="w-12 h-12" />}
            title="暂无编排任务" 
            description="点击上方新建任务按钮开始第一条视频创作"
            action={{ label: '立即创建', onClick: () => setIsDialogOpen(true) }}
          />
        )}

        {state.status === 'success' && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {state.data.map(task => (
              <TaskCard key={task.id} task={task} />
            ))}
          </div>
        )}
      </div>

      <TaskCreateDialog 
        isOpen={isDialogOpen} 
        onClose={() => setIsDialogOpen(false)} 
        onSuccess={() => {
          setIsDialogOpen(false);
          actions.refresh();
        }}
        moduleType={activeTab}
      />
    </div>
  );
}

function TaskCard({ task }: { task: TaskListViewModel }) {
  const isFinished = task.status === 'success' || task.status === 'failed';
  
  return (
    <Link to={`/task/${task.id}`} className="group relative glass rounded-xl overflow-hidden hover:border-primary/50 transition-all block hover:-translate-y-1 hover:shadow-[0_8px_30px_rgb(0,0,0,0.5)]">
      <div className="h-40 bg-black overflow-hidden relative border-b border-white/5">
        {task.thumbnail ? (
          <img src={task.thumbnail} alt="thumbnail" className="w-full h-full object-cover opacity-60 group-hover:opacity-100 transition-opacity duration-300 group-hover:scale-105" />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-card-border/30 text-foreground/20">
            <Video className="w-12 h-12 stroke-1" />
          </div>
        )}
        
        {/* Play Overlay */}
        {task.status === 'success' && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/20 opacity-0 group-hover:opacity-100 transition-opacity">
            <div className="w-12 h-12 rounded-full bg-primary flex items-center justify-center shadow-lg">
              <Play className="w-6 h-6 text-white ml-1" />
            </div>
          </div>
        )}

        {/* Status Badge */}
        <div className="absolute top-3 left-3 px-3 py-1 rounded-full text-xs font-medium backdrop-blur-md shadow-sm"
          style={{ backgroundColor: `var(--${task.statusColor}-500, rgba(255,255,255,0.1))` }}>
          <div className="flex items-center gap-1.5 text-white">
            {!isFinished && <div className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />}
            {task.statusLabel}
          </div>
        </div>
      </div>
      
      <div className="p-4 border-t border-white/5">
        <div className="flex items-center justify-between mb-3 text-xs text-foreground/50">
          <span className="font-mono">{task.id}</span>
          <span>{task.createdAtFormatted}</span>
        </div>
        
        {!isFinished && (
          <div className="mb-2">
            <div className="flex justify-between text-xs mb-1.5">
              <span className="text-foreground/70">总进度</span>
              <span className="font-mono">{task.progress}%</span>
            </div>
            <div className="w-full bg-black/40 rounded-full h-1.5 overflow-hidden">
              <div 
                className="bg-primary h-full rounded-full transition-all duration-500 ease-out"
                style={{ width: `${task.progress}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex gap-2 mt-4">
          {task.platforms.map(p => (
            <span key={p} className="text-[10px] uppercase font-semibold text-foreground/40 bg-white/5 px-2 py-0.5 rounded border border-white/10">
              {p}
            </span>
          ))}
        </div>
      </div>
    </Link>
  );
}
