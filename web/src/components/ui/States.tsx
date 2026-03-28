// src/components/ui/States.tsx
import React from 'react';
import { AlertCircle, RotateCcw, FileQuestion } from 'lucide-react';
import { cn } from '../../lib/utils';

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-white/10", className)} />;
}

export function ErrorState({ message, action }: { message: string, action?: { label: string, onClick: () => void } }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
      <div className="bg-red-500/10 p-4 rounded-full mb-4">
        <AlertCircle className="w-10 h-10 text-red-500" />
      </div>
      <h3 className="text-xl font-medium text-foreground mb-2">出错了</h3>
      <p className="text-foreground/70 mb-6 max-w-md">{message}</p>
      {action && (
        <button 
          onClick={action.onClick}
          className="flex items-center gap-2 bg-primary hover:bg-primary-hover text-white px-6 py-2 rounded-lg transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          {action.label}
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon, title, description, action }: { icon?: React.ReactNode, title: string, description: string, action?: { label: string, onClick: () => void } }) {
  return (
    <div className="flex flex-col items-center justify-center py-20 px-4 text-center border border-dashed border-white/20 rounded-xl bg-white/5">
      <div className="text-foreground/40 mb-4">
        {icon || <FileQuestion className="w-12 h-12" />}
      </div>
      <h3 className="text-xl font-medium text-foreground mb-2">{title}</h3>
      <p className="text-foreground/60 mb-6">{description}</p>
      {action && (
        <button 
          onClick={action.onClick}
          className="bg-primary hover:bg-primary-hover text-white px-6 py-2 rounded-lg transition-colors font-medium shadow-lg shadow-primary/20"
        >
          {action.label}
        </button>
      )}
    </div>
  );
}
