import React from 'react';
import type { RuntimeStep, Problem, TestSuite, TestCase, Analysis, ExecutionAttempt } from '@/lib/types';
import { RuntimeInspector } from './RuntimeInspector';
import { ProblemsList } from './ProblemsList';
import { TestInfo } from './TestInfo';
import { AnalysisDisplay } from './AnalysisDisplay';
import { ExecutionTimeline } from './ExecutionTimeline';
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
  suite?: TestSuite;
  testCase?: TestCase;
  analysis?: Analysis;
  attempts?: ExecutionAttempt[];
}

export const LeftPanel: React.FC<LeftPanelProps> = ({
  steps,
  problems,
  activeStepId,
  onStepSelect,
  isCollapsed,
  suite,
  testCase,
  analysis,
  attempts,
}) => {
  // If collapsed, we hide the content entirely (width is handled by parent ResizablePanel collapsedSize=0)
  if (isCollapsed) {
    return null;
  }

  const hasTestInfo = suite || testCase;
  const hasAnalysis = analysis;
  const hasTimeline = attempts && attempts.length > 0;

  return (
    <div className="h-full w-full border-r border-border bg-card flex flex-col overflow-hidden">
      {/* Test Info, Analysis, and Timeline at the top */}
      {(hasTestInfo || hasAnalysis || hasTimeline) && (
        <div className="flex-shrink-0 overflow-y-auto border-b border-border max-h-[60%]">
          {hasTestInfo && <TestInfo suite={suite} testCase={testCase} />}
          {hasTimeline && <ExecutionTimeline attempts={attempts} />}
          {hasAnalysis && <AnalysisDisplay analysis={analysis} />}
        </div>
      )}
      
      {/* Runtime Inspector and Problems below */}
      <div className="flex-1 min-h-0">
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
    </div>
  );
};
