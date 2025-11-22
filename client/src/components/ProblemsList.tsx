import React from 'react';
import type { Problem } from '@/lib/types';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, AlertCircle } from 'lucide-react';

interface ProblemsListProps {
  problems: Problem[];
  activeStepId: string | null;
  onProblemSelect: (stepId: string) => void;
}

export const ProblemsList: React.FC<ProblemsListProps> = ({
  problems,
  activeStepId,
  onProblemSelect,
}) => {
  const [isOpen, setIsOpen] = React.useState(true);

  return (
    <div className="flex flex-col h-full border-t border-border">
      <div 
        className="flex items-center px-4 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50 select-none border-b border-border"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <span className="text-xs font-bold tracking-wider text-muted-foreground">PROBLEMS</span>
        {problems.length > 0 && (
          <span className="ml-2 bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">{problems.length}</span>
        )}
      </div>
      
      {isOpen && (
        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <div className="overflow-auto h-full">
            {problems.length === 0 ? (
               <div className="px-8 py-4 text-xs text-muted-foreground italic">No problems found.</div>
            ) : (
              problems.map((problem) => {
                const isActive = problem.stepId === activeStepId;
                return (
                  <div
                    key={problem.id}
                    className={cn(
                      "flex gap-2 px-4 py-2 border-b border-border/50 cursor-pointer hover:bg-muted/30 transition-colors",
                      isActive && "bg-accent text-accent-foreground"
                    )}
                    onClick={() => onProblemSelect(problem.stepId)}
                  >
                    <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
                    <div className="flex flex-col min-w-0">
                      <div className="text-xs font-medium truncate">{problem.description}</div>
                      <div className="text-[10px] text-muted-foreground">
                         {problem.blockId} @ step {problem.stepId}
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>
      )}
    </div>
  );
};
