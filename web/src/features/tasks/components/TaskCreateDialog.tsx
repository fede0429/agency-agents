import React, { useState } from 'react';
import { X, Loader2, CheckCircle2 } from 'lucide-react';
import { fetchApi } from '../../../lib/api';

export function TaskCreateDialog({ isOpen, onClose, onSuccess, moduleType }: { isOpen: boolean, onClose: () => void, onSuccess: () => void, moduleType: string }) {
  const [url, setUrl] = useState('');
  const [platforms, setPlatforms] = useState<string[]>(['tiktok']);
  const [style, setStyle] = useState('premium');
  
  const [status, setStatus] = useState<'idle' | 'submitting' | 'success' | 'error'>('idle');
  const [errorMsg, setErrorMsg] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!url) return;

    setStatus('submitting');
    setErrorMsg('');

    try {
      const res = await fetchApi('/tasks', {
        method: 'POST',
        body: JSON.stringify({
          target_url: url,
          publish_platforms: platforms,
          video_style: style,
          module_type: moduleType
        })
      });

      if (!res.success) {
        setStatus('error');
        setErrorMsg(res.error?.message || '未知错误');
        return;
      }

      setStatus('success');
      setTimeout(() => {
        onSuccess();
        setStatus('idle');
        setUrl('');
      }, 1000);
    } catch (err: any) {
      setStatus('error');
      setErrorMsg(err.message);
    }
  };

  const togglePlatform = (p: string) => {
    setPlatforms(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-card glass border border-white/10 rounded-2xl w-full max-w-lg shadow-2xl relative overflow-hidden animate-in zoom-in-95 duration-200">
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/5">
          <h2 className="text-xl font-semibold">
            {moduleType === 'ugc' ? '新建 UGC带货视频' : moduleType === 'anime' ? '新建 动漫剧集' : '新建 综合短视频'}
          </h2>
          <button onClick={onClose} disabled={status === 'submitting'} className="text-foreground/50 hover:text-foreground transition-colors disabled:opacity-50">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Body */}
        <form onSubmit={handleSubmit} className="p-6">
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-foreground/80 mb-1.5">目标商品/竞品链接</label>
              <input 
                type="url" 
                required
                value={url}
                onChange={e => setUrl(e.target.value)}
                placeholder="https://v.douyin.com/..."
                className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-foreground placeholder:text-foreground/30 focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all font-mono text-sm"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground/80 mb-2">发布平台 (多选)</label>
              <div className="flex gap-3">
                {['tiktok', 'youtube'].map(p => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => togglePlatform(p)}
                    className={`flex-1 py-2 rounded-lg text-sm font-medium border transition-all
                      ${platforms.includes(p) 
                        ? 'bg-primary/20 border-primary text-primary shadow-[0_0_15px_rgba(59,130,246,0.2)]' 
                        : 'bg-black/40 border-white/10 text-foreground/50 hover:border-white/20'}`}
                  >
                    {p.toUpperCase()}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-foreground/80 mb-2">生成质量策略</label>
              <select 
                value={style}
                onChange={e => setStyle(e.target.value)}
                className="w-full bg-black/40 border border-white/10 rounded-lg px-4 py-2.5 text-foreground focus:outline-none focus:ring-2 focus:ring-primary/50 transition-all appearance-none"
              >
                <option value="economy">Economy (快速, 低成本)</option>
                <option value="premium">Premium (高质量, Kimi+Kling)</option>
                <option value="china">China (国内定制)</option>
              </select>
            </div>
            
            {status === 'error' && (
              <div className="text-sm text-red-400 bg-red-400/10 px-4 py-2.5 rounded-lg border border-red-400/20">
                {errorMsg}
              </div>
            )}
          </div>

          <div className="mt-8">
            <button
              type="submit"
              disabled={status === 'submitting' || !url || platforms.length === 0}
              className="w-full bg-primary hover:bg-primary-hover disabled:bg-primary/50 disabled:cursor-not-allowed text-white py-3 rounded-lg font-medium shadow-lg shadow-primary/20 transition-all flex items-center justify-center gap-2"
            >
              {status === 'submitting' ? (
                <><Loader2 className="w-5 h-5 animate-spin" /> 任务下发中...</>
              ) : status === 'success' ? (
                <><CheckCircle2 className="w-5 h-5 text-green-400" /> 创建成功</>
              ) : (
                '立即生成视频'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
