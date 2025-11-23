import React from 'react';
import type { Analysis } from '@/lib/types';
import { ChevronDown, ChevronRight, Brain, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface AnalysisDisplayProps {
  analysis?: Analysis;
}

export const AnalysisDisplay: React.FC<AnalysisDisplayProps> = ({ analysis }) => {
  const [isOpen, setIsOpen] = React.useState(true);

  if (!analysis) {
    return null;
  }

  const hasFailedTest = !!analysis.failed_test;

  return (
    <div className="flex flex-col border-b border-border bg-card">
      <div 
        className={cn(
          "flex items-center px-4 py-2 cursor-pointer hover:bg-muted/50 select-none",
          hasFailedTest ? "bg-destructive/10" : "bg-muted/30"
        )}
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <Brain className="h-4 w-4 mr-2" />
        <span className="text-xs font-bold tracking-wider text-muted-foreground">ANALYSIS</span>
        {hasFailedTest && (
          <AlertCircle className="h-4 w-4 ml-2 text-destructive" />
        )}
      </div>
      
      {isOpen && (
        <div className="px-4 py-3 space-y-4 text-xs">
          {analysis.task_description && (
            <div className="space-y-2">
              <div className="font-semibold text-foreground">Task Description</div>
              <div className="text-muted-foreground text-[11px] leading-relaxed pl-2 border-l-2 border-border">
                {analysis.task_description}
              </div>
            </div>
          )}

          {analysis.failed_test && (
            <div className="space-y-2 pt-2 border-t border-border">
              <div className="flex items-center gap-2">
                <AlertCircle className="h-3 w-3 text-destructive" />
                <div className="font-semibold text-destructive">Failed Test</div>
              </div>
              <div className="space-y-2 text-muted-foreground">
                <div>
                  <span className="font-medium">Test Name:</span> {analysis.failed_test.name}
                </div>
                {analysis.failed_test.input && (
                  <div>
                    <span className="font-medium">Input:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] font-mono overflow-x-auto border border-border">
                      {analysis.failed_test.input}
                    </pre>
                  </div>
                )}
                {analysis.failed_test.expected && (
                  <div>
                    <span className="font-medium">Expected:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] font-mono overflow-x-auto border border-border">
                      {analysis.failed_test.expected}
                    </pre>
                  </div>
                )}
                {analysis.failed_test.actual && (
                  <div>
                    <span className="font-medium text-destructive">Actual:</span>
                    <pre className="mt-1 p-2 bg-destructive/10 border border-destructive/20 rounded text-[10px] font-mono overflow-x-auto">
                      {analysis.failed_test.actual}
                    </pre>
                  </div>
                )}
                {analysis.failed_test.notes && (
                  <div>
                    <span className="font-medium">Notes:</span>
                    <pre className="mt-1 p-2 bg-muted rounded text-[10px] font-mono overflow-x-auto border border-border whitespace-pre-wrap">
                      {analysis.failed_test.notes}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          )}

          {!hasFailedTest && analysis.task_description && (
            <div className="text-muted-foreground text-[11px] italic">
              No test failures detected.
            </div>
          )}
        </div>
      )}
    </div>
  );
};

