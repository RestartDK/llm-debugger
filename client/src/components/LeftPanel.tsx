import React from 'react';
import type { RuntimeStep, Problem } from '@/lib/types';
import { RuntimeInspector } from './RuntimeInspector';
import { ProblemsList } from './ProblemsList';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';

interface LeftPanelProps {
  steps: RuntimeStep[];
  problems: Problem[];
  activeStepId: string | null;
  onStepSelect: (stepId: string) => void;
  isCollapsed: boolean;
}

export const LeftPanel: React.FC<LeftPanelProps> = ({
  steps,
  problems,
  activeStepId,
  onStepSelect,
  isCollapsed,
}) => {
  // If collapsed, we hide the content entirely (width is handled by parent ResizablePanel collapsedSize=0)
  if (isCollapsed) {
    return null;
  }

  return (
    <div className="h-full w-full border-r border-border bg-card">
      <ResizablePanelGroup direction="vertical">
        <ResizablePanel defaultSize={70} minSize={30}>
          <RuntimeInspector
            steps={steps}
            activeStepId={activeStepId}
            onStepSelect={onStepSelect}
            problems={problems}
          />
        </ResizablePanel>
        
        <ResizableHandle className="h-1 bg-transparent hover:bg-primary/10 transition-colors" />
        
        <ResizablePanel defaultSize={30} minSize={15}>
          <ProblemsList
            problems={problems}
            activeStepId={activeStepId}
            onProblemSelect={onStepSelect}
          />
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
};
