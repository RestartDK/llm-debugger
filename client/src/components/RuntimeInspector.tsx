import React from 'react';
import type { RuntimeStep, Problem } from '@/lib/types';
import { cn } from '@/lib/utils';
import { ChevronDown, ChevronRight, CircleCheck, CircleX, Loader2, AlertTriangle } from 'lucide-react';

interface RuntimeInspectorProps {
  steps: RuntimeStep[];
  activeStepId: string | null;
  onStepSelect: (stepId: string) => void;
  problems?: Problem[];
}

const StatusIcon = ({ status }: { status: RuntimeStep['status'] }) => {
  switch (status) {
    case 'succeeded':
      return <CircleCheck className="h-3 w-3 shrink-0 text-green-500" />;
    case 'failed':
      return <CircleX className="h-3 w-3 shrink-0 text-red-500" />;
    case 'pending':
      return <Loader2 className="h-3 w-3 shrink-0 text-yellow-500 animate-spin" />;
  }
};

export const RuntimeInspector: React.FC<RuntimeInspectorProps> = ({
  steps,
  activeStepId,
  onStepSelect,
  problems = [],
}) => {
  const [isOpen, setIsOpen] = React.useState(true);
  
  return (
    <div className="flex flex-col h-full">
      <div 
        className="flex items-center px-4 py-2 bg-muted/30 cursor-pointer hover:bg-muted/50 select-none border-b border-border"
        onClick={() => setIsOpen(!isOpen)}
      >
        {isOpen ? <ChevronDown className="h-4 w-4 mr-2" /> : <ChevronRight className="h-4 w-4 mr-2" />}
        <span className="text-xs font-bold tracking-wider text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">RUNTIME STATE INSPECTOR</span>
      </div>
      
      {isOpen && (
        <div className="flex flex-col flex-1 min-h-0 overflow-hidden">
          <div className="overflow-auto h-full">
            <table className="min-w-full w-full text-xs text-left table-fixed border-collapse">
              <thead className="bg-background sticky top-0 z-10 shadow-xs">
                <tr>
                  <th className="px-2 py-1.5 font-medium text-muted-foreground w-[50px] min-w-[50px] whitespace-nowrap overflow-hidden text-ellipsis">Step</th>
                  <th className="px-2 py-1.5 font-medium text-muted-foreground w-[100px] min-w-[100px] whitespace-nowrap overflow-hidden text-ellipsis">Status</th>
                  <th className="px-2 py-1.5 font-medium text-muted-foreground w-[120px] min-w-[100px] whitespace-nowrap overflow-hidden text-ellipsis">Block/Code</th>
                  <th className="px-2 py-1.5 font-medium text-muted-foreground min-w-[100px] whitespace-nowrap overflow-hidden text-ellipsis">Before</th>
                  <th className="px-2 py-1.5 font-medium text-muted-foreground min-w-[100px] whitespace-nowrap overflow-hidden text-ellipsis">After</th>
                </tr>
              </thead>
              <tbody>
                {steps.map((step, index) => {
                  const isActive = step.id === activeStepId;
                  const statusLabel =
                    step.status.charAt(0).toUpperCase() + step.status.slice(1);
                  // Check if this step has a warning
                  const hasWarning = problems.some(p => p.stepId === step.id && p.severity === 'warning');
                  
                  return (
                    <tr 
                      key={step.id}
                      className={cn(
                        "border-b border-border/50 cursor-pointer hover:bg-muted/30 transition-colors",
                        isActive && "bg-accent text-accent-foreground"
                      )}
                      onClick={() => onStepSelect(step.id)}
                    >
                      <td className="px-2 py-1.5 align-top text-muted-foreground whitespace-nowrap overflow-hidden text-ellipsis">
                        {index + 1}
                      </td>
                      <td className="px-2 py-1.5 align-top whitespace-nowrap overflow-hidden text-ellipsis">
                        <div className="flex items-center gap-2">
                          <StatusIcon status={step.status} />
                          {hasWarning && (
                            <AlertTriangle className="h-3 w-3 shrink-0 text-yellow-500" />
                          )}
                          <span className="text-[10px] font-semibold uppercase">
                            {statusLabel}
                          </span>
                        </div>
                      </td>
                      <td className="px-2 py-1.5 align-top overflow-hidden">
                         <div className="font-semibold truncate">{step.blockName}</div>
                         <div className="font-mono text-[10px] text-muted-foreground truncate">{step.codeSnippet}</div>
                      </td>
                      <td className="px-2 py-1.5 align-top font-mono text-[10px] whitespace-nowrap overflow-hidden text-ellipsis">
                        {Object.entries(step.before).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')}
                      </td>
                      <td className="px-2 py-1.5 align-top font-mono text-[10px] whitespace-nowrap overflow-hidden text-ellipsis">
                        {Object.entries(step.after).map(([k, v]) => `${k}=${JSON.stringify(v)}`).join(', ')}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
};
