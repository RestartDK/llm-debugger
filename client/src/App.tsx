import { useState, useRef } from 'react';
import { LeftPanel } from './components/LeftPanel';
import { CfgCanvas } from './components/CfgCanvas';
import { mockSteps, mockProblems, initialNodes, initialEdges } from './lib/mockData';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import type { ImperativePanelHandle } from 'react-resizable-panels';
import { ChevronLeft, ChevronRight } from 'lucide-react';

function App() {
  // Debugger Data (Mocked for now, would come from API)
  const [steps] = useState(mockSteps);
  const [problems] = useState(mockProblems);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  
  const leftPanelRef = useRef<ImperativePanelHandle>(null);
  
  // Selection State
  const [activeStepId, setActiveStepId] = useState<string | null>('score-step-21'); // Start with a failure selected
  const [activeNodeId, setActiveNodeId] = useState<string | null>('score-block-aggregate');

  // Sync Node selection when Step is selected
  const handleStepSelect = (stepId: string) => {
    setActiveStepId(stepId);
    const step = steps.find(s => s.id === stepId);
    if (step) {
      setActiveNodeId(step.blockId);
    }
  };

  // Sync Step selection when Node is clicked
  const handleNodeClick = (nodeId: string) => {
    setActiveNodeId(nodeId);
    
    // Logic: Find the most "interesting" step for this node.
    // Priority: First Failed Step -> Last Executed Step -> First Step
    const nodeSteps = steps.filter(s => s.blockId === nodeId);
    
    if (nodeSteps.length > 0) {
      const failedStep = nodeSteps.find(s => s.status === 'failed');
      if (failedStep) {
        setActiveStepId(failedStep.id);
      } else {
        // Default to last step (latest state)
        setActiveStepId(nodeSteps[nodeSteps.length - 1].id);
      }
    } else {
      // No steps for this node (maybe unreachable or static?)
      setActiveStepId(null);
    }
  };
  
  const toggleSidebar = () => {
    const panel = leftPanelRef.current;
    if (panel) {
      if (isSidebarCollapsed) {
        panel.expand();
      } else {
        panel.collapse();
      }
    }
  };

  return (
    <div className="h-screen w-screen bg-background text-foreground relative">
      <ResizablePanelGroup
        direction="horizontal"
        className="h-full w-full"
      >
        <ResizablePanel 
          ref={leftPanelRef}
          defaultSize={28} 
          minSize={20} 
          maxSize={40}
          collapsible={true}
          collapsedSize={0}
          onCollapse={() => setIsSidebarCollapsed(true)}
          onExpand={() => setIsSidebarCollapsed(false)}
          className={isSidebarCollapsed ? "min-w-0 transition-all duration-300 ease-in-out" : "transition-all duration-300 ease-in-out"}
        >
          <LeftPanel
            steps={steps}
            problems={problems}
            activeStepId={activeStepId}
            onStepSelect={handleStepSelect}
            isCollapsed={isSidebarCollapsed}
          />
        </ResizablePanel>

        <ResizableHandle withHandle={!isSidebarCollapsed} />

        <ResizablePanel defaultSize={72} minSize={40}>
          <div className="h-full w-full relative">
            {/* Toggle Button */}
            <div 
              className="absolute left-4 top-4 z-50 bg-background border border-border rounded-md p-1 cursor-pointer shadow-sm hover:bg-accent"
              onClick={toggleSidebar}
            >
              {isSidebarCollapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
            </div>

            <CfgCanvas
              initialNodes={initialNodes}
              initialEdges={initialEdges}
              activeNodeId={activeNodeId}
              onNodeClick={handleNodeClick}
              problems={problems}
            />
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}

export default App;
