import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, ExternalLink, PlayCircle, CheckCircle, Clock, FileText, Video, RefreshCw, XCircle } from 'lucide-react';
import { useTaskDetail } from '../features/tasks/hooks/useTaskDetail';
import { Skeleton, ErrorState } from '../components/ui/States';
import { cn } from '../lib/utils';

export function TaskDetailPage() {
  const { taskId } = useParams<{ taskId: string }>();
  const { state, refetch } = useTaskDetail(taskId || '');

  if (state.status === 'loading') {
    return <div className="p-10"><Skeleton className="h-96" /></div>;
  }

  if (state.status === 'error') {
    return <ErrorState message={state.message} action={{ label: '重试', onClick: refetch }} />;
  }

  if (state.status !== 'success' || !state.data) return null;

  const task = state.data;
  const isFinished = task.status === 'success' || task.status === 'failed';

  return (
    <div className="max-w-6xl mx-auto py-8 px-6">
      
      {/* Header */}
      <div className="flex items-center gap-4 mb-8">
        <Link to="/" className="p-2 bg-white/5 hover:bg-white/10 rounded-full transition-colors">
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-2xl font-bold">{task.title}</h1>
            <span className={cn(
              "px-3 py-1 text-xs rounded-full font-medium border flex items-center gap-1.5",
              task.status === 'failed' ? "bg-red-500/10 text-red-400 border-red-500/20" :
              task.status === 'success' ? "bg-green-500/10 text-green-400 border-green-500/20" :
              "bg-primary/10 text-primary border-primary/20"
            )}>
              {!isFinished ? <RefreshCw className="w-3 h-3 animate-spin" /> : null}
              {task.statusLabel}
            </span>
          </div>
          <div className="flex items-center gap-4 text-sm text-foreground/50 mt-1">
            <span className="font-mono">{task.id}</span>
            <span>{task.createdAtFormatted}</span>
            {task.sourceUrl && (
              <a href={task.sourceUrl} target="_blank" rel="noreferrer" className="flex items-center gap-1 hover:text-primary transition-colors">
                <ExternalLink className="w-3.5 h-3.5" /> 原始素材
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        
        {/* Left Column: Timeline */}
        <div className="lg:col-span-1">
          <div className="glass rounded-xl p-6 h-full">
            <h3 className="text-lg font-medium mb-6 flex items-center gap-2">
              <Clock className="w-5 h-5 text-primary" /> 执行轨道
            </h3>
            
            <div className="relative pl-3 space-y-8 before:absolute before:inset-0 before:ml-5 before:-translate-x-px md:before:mx-auto md:before:translate-x-0 before:h-full before:w-0.5 before:bg-gradient-to-b before:from-transparent before:via-white/10 before:to-transparent">
              {task.timeline.map((node) => (
                <div key={node.step} className="relative z-10">
                  <div className="flex items-start gap-4">
                    <div className={cn(
                      "w-6 h-6 rounded-full flex items-center justify-center shrink-0 mt-0.5 border-2 transition-all duration-500",
                      node.status === 'success' ? "bg-green-500 border-green-400 text-white shadow-[0_0_15px_rgba(34,197,94,0.4)]" :
                      node.status === 'failed' ? "bg-red-500 border-red-400 text-white shadow-[0_0_15px_rgba(239,68,68,0.4)]" :
                      node.status === 'processing' ? "bg-card border-primary text-primary shadow-[0_0_15px_rgba(99,102,241,0.5)] animate-pulse-slow" :
                      "bg-card border-white/10 text-white/20"
                    )}>
                      {node.status === 'success' ? <CheckCircle className="w-3.5 h-3.5" /> :
                       node.status === 'failed' ? <XCircle className="w-3.5 h-3.5" /> : 
                       <div className="w-2 h-2 rounded-full bg-current" />}
                    </div>
                    
                    <div className="flex-1 pb-1">
                      <h4 className={cn("text-base font-medium", 
                        node.status === 'pending' ? "text-foreground/40" : "text-foreground"
                      )}>{node.stepLabel}</h4>
                      
                      {node.status === 'processing' && (
                        <div className="mt-2 text-xs font-semibold tracking-wide text-transparent bg-clip-text bg-gradient-to-r from-primary to-purple-400 flex items-center gap-1.5 animate-shimmer" style={{ backgroundSize: '200% auto' }}>
                          <RefreshCw className="w-3 h-3 animate-spin text-primary" /> 引擎合成流转中...
                        </div>
                      )}
                      
                      {node.tookMs && (
                        <p className="text-xs text-foreground/40 mt-1">{Math.round(node.tookMs / 1000)}s</p>
                      )}

                      {node.error && (
                        <div className="mt-2 text-xs text-red-200 bg-red-500/10 border border-red-500/20 p-3 rounded-lg leading-relaxed">
                          {node.error}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Artifacts */}
        <div className="lg:col-span-2 space-y-6">
          
          {/* Video Preview */}
          <div className="glass shadow-2xl rounded-xl overflow-hidden border border-white/10 relative group">
            <div className="absolute inset-0 bg-gradient-to-tr from-primary/10 to-transparent opacity-0 group-hover:opacity-100 transition duration-700 pointer-events-none"></div>
            <div className="p-4 border-b border-white/5 bg-white/5 flex items-center gap-2">
              <Video className="w-4 h-4 text-foreground/60" />
              <h3 className="font-medium text-sm">最终全息影像</h3>
            </div>
            <div className="aspect-video bg-black relative flex items-center justify-center">
              {task.videoUrl ? (
                <video src={task.videoUrl} controls className="w-full h-full object-contain" />
              ) : task.status === 'failed' ? (
                <div className="text-foreground/30 flex flex-col items-center gap-2">
                  <XCircle className="w-10 h-10 mb-2" />
                  未能生成最终视频
                </div>
              ) : (
                <div className="text-foreground/30 flex flex-col items-center gap-2">
                  <PlayCircle className="w-10 h-10 mb-2 opacity-50" />
                  视频生成中...请稍候
                </div>
              )}
            </div>
          </div>

          {/* Script Output */}
          <div className="glass shadow-2xl rounded-xl overflow-hidden border border-white/10 mt-6 relative">
            <div className="p-4 border-b border-white/5 bg-white/5 flex items-center gap-2">
              <FileText className="w-4 h-4 text-foreground/60" />
              <h3 className="font-medium text-sm">核心解说剧本</h3>
            </div>
            <div className="p-6 bg-card/60 backdrop-blur-sm">
              {task.script ? (
                <p className="text-sm leading-relaxed whitespace-pre-wrap font-mono text-foreground/80">
                  {task.script}
                </p>
              ) : (
                <p className="text-sm text-foreground/30 italic">脚本准备中...</p>
              )}
            </div>
          </div>

        </div>

      </div>
    </div>
  );
}
