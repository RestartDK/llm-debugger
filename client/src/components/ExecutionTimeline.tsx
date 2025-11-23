import React from 'react';
import type { ExecutionAttempt } from '@/lib/types';
import { ChevronDown, ChevronRight, History, CheckCircle2, ArrowRight } from 'lucide-react';
import { cn } from '@/lib/utils';

interface ExecutionTimelineProps {
  attempts?: ExecutionAttempt[];
}

export const ExecutionTimeline: React.FC<ExecutionTimelineProps> = ({ attempts }) => {
  const [isOpen, setIsOpen] = React.useState(true);

  if (!attempts || attempts.length === 0) {
    return null;
  }

  return (
    <div className="flex flex-col border-b border-border bg-card">
      <div 
        className="flex items-center px-4 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50 select-none"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <History className="h-4 w-4 mr-2" />
        <span className="text-xs font-bold tracking-wider text-muted-foreground">EXECUTION TIMELINE</span>
        <span className="ml-auto text-[10px] text-muted-foreground font-mono bg-muted px-1.5 py-0.5 rounded">
          {attempts.length} attempt{attempts.length !== 1 ? 's' : ''}
        </span>
      </div>
      
      {isOpen && (
        <div className="px-4 py-4 space-y-0 relative">
          {/* Vertical line connecting dots */}
          <div className="absolute left-[27px] top-4 bottom-4 w-[1px] bg-border" />

          {attempts.map((attempt, index) => {
            const isLast = index === attempts.length - 1;
            const isSuccess = attempt.status === 'success';

            return (
              <div key={attempt.attempt_number} className="relative flex gap-4 pb-6 last:pb-0 group">
                {/* Icon/Dot */}
                <div className={cn(
                  "relative z-10 flex items-center justify-center w-6 h-6 rounded-full border-2 bg-card shrink-0 transition-colors",
                  isSuccess 
                    ? "border-green-500 text-green-500" 
                    : isLast 
                      ? "border-destructive text-destructive" 
                      : "border-muted-foreground text-muted-foreground"
                )}>
                  {isSuccess ? (
                    <CheckCircle2 className="w-3.5 h-3.5" />
                  ) : (
                    <span className="text-[10px] font-bold font-mono">{attempt.attempt_number}</span>
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 pt-0.5 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={cn(
                      "text-xs font-medium",
                      isSuccess ? "text-green-500" : "text-foreground"
                    )}>
                      Attempt {attempt.attempt_number}
                    </span>
                    {isSuccess && (
                      <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-green-500/10 text-green-500 font-medium">
                        Success
                      </span>
                    )}
                  </div>

                  {attempt.error_summary && (
                    <div className="text-[11px] text-destructive bg-destructive/5 p-2 rounded border border-destructive/20 mb-2">
                      {attempt.error_summary}
                    </div>
                  )}

                  {/* Show what fix was applied *after* this attempt failed, if there is a next attempt */}
                  {/* Wait, the reasoning is stored on the NEXT attempt usually, or we look at reasoning of current attempt? */}
                  {/* The reasoning field in ExecutionAttempt represents "why this fix was applied" to CREATE this attempt. */}
                  {attempt.reasoning && (
                    <div className="flex gap-2 mt-2 text-[11px] text-muted-foreground bg-muted/30 p-2 rounded border border-border/50">
                      <ArrowRight className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                      <div>
                        <span className="font-medium text-foreground/80">Fix applied:</span>
                        <p className="mt-0.5 leading-relaxed">{attempt.reasoning}</p>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};

