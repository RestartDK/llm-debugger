import { useEffect, useRef, useState } from 'react';
import type { Edge, Node } from '@xyflow/react';
import { LeftPanel } from './components/LeftPanel';
import { CfgCanvas } from './components/CfgCanvas';
import {
  executeTestCases,
  fetchControlFlow,
  convertNodesToBlocks,
  extractSourcesFromNodes,
} from './lib/api';
import { layoutCfgNodes } from './lib/utils';
import type {
  CfgNodeData,
  Problem,
  RuntimeStep,
  TestSuite,
  TestCase,
  Analysis,
  ExecutionAttempt,
} from './lib/types';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import type { ImperativePanelHandle } from 'react-resizable-panels';
import { ChevronLeft, ChevronRight } from 'lucide-react';

function App() {
  const [steps, setSteps] = useState<RuntimeStep[]>([]);
  const [problems, setProblems] = useState<Problem[]>([]);
  const [nodes, setNodes] = useState<Node<CfgNodeData>[]>([]);
  const [edges, setEdges] = useState<Edge[]>([]);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [cfgLoading, setCfgLoading] = useState(true);
  const [cfgError, setCfgError] = useState<string | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);
  const [taskDescription, setTaskDescription] = useState<string | undefined>(
    undefined,
  );
  const [suite, setSuite] = useState<TestSuite | undefined>(undefined);
  const [testCase, setTestCase] = useState<TestCase | undefined>(undefined);
  const [analysis, setAnalysis] = useState<Analysis | undefined>(undefined);
  const [attempts, setAttempts] = useState<ExecutionAttempt[] | undefined>(undefined);

  const leftPanelRef = useRef<ImperativePanelHandle>(null);
  
  // Selection State
  const [activeStepId, setActiveStepId] = useState<string | null>(null);
  const [activeNodeId, setActiveNodeId] = useState<string | null>(null);

  useEffect(() => {
    if (activeNodeId && nodes.every((node) => node.id !== activeNodeId)) {
      setActiveNodeId(nodes[0]?.id ?? null);
    }
  }, [activeNodeId, nodes]);

  useEffect(() => {
    if (steps.length === 0) {
      if (activeStepId !== null) {
        setActiveStepId(null);
      }
      return;
    }
    if (activeStepId && steps.every((step) => step.id !== activeStepId)) {
      setActiveStepId(steps[0].id);
    }
  }, [activeStepId, steps]);

  const mergeNodesWithAnalysis = (
    current: Node<CfgNodeData>[],
    updates?: Node<CfgNodeData>[],
  ): Node<CfgNodeData>[] => {
    if (!updates || updates.length === 0) {
      return current;
    }

    const updateMap = new Map(updates.map((node) => [node.id, node]));
    const existingIds = new Set(current.map((node) => node.id));

    const merged = current.map((node) => {
      const update = updateMap.get(node.id);
      if (!update) {
        return node;
      }
      return {
        ...node,
        data: {
          ...node.data,
          ...update.data,
        },
      };
    });

    // Append any nodes that were only present in the analysis payload.
    updates.forEach((node) => {
      if (!existingIds.has(node.id)) {
        merged.push(node);
        existingIds.add(node.id);
      }
    });

    return merged;
  };

  const handleAnalysisSuccess = (payload: Awaited<ReturnType<typeof executeTestCases>>) => {
    setSteps(payload.steps ?? []);
    setProblems(payload.problems ?? []);
    setSuite(payload.suite);
    setTestCase(payload.test_case);
    setAnalysis(payload.analysis);
    setAttempts(payload.attempts);

    setNodes((prev) => mergeNodesWithAnalysis(prev, payload.nodes));

    if (payload.edges && payload.edges.length > 0) {
      setEdges(payload.edges);
    }

    if (payload.problems && payload.problems.length > 0) {
      const firstProblem = payload.problems[0];
      setActiveNodeId(firstProblem.blockId || null);
      setActiveStepId(firstProblem.stepId || null);
      return;
    }

    if (payload.steps && payload.steps.length > 0) {
      const lastStep = payload.steps[payload.steps.length - 1];
      setActiveNodeId(lastStep.blockId);
      setActiveStepId(lastStep.id);
      return;
    }

    if (payload.nodes && payload.nodes.length > 0) {
      setActiveNodeId(payload.nodes[0].id);
      setActiveStepId(null);
    }
  };

  const runAnalysis = async () => {
    setAnalysisLoading(true);
    setAnalysisError(null);
    try {
      // Convert nodes to blocks format
      const blocks = convertNodesToBlocks(nodes);
      
      // Extract sources from nodes
      const sources = extractSourcesFromNodes(nodes);
      
      // Use task_description from GET response, or fallback to default
      const task_description =
        taskDescription || 'Investigate generated test failure';
      
      console.log('[App] Running analysis with:', {
        task_description,
        blocksCount: blocks.length,
        sourcesCount: sources.length,
      });
      
      const payload = await executeTestCases({
        task_description,
        blocks,
        sources,
      });
      handleAnalysisSuccess(payload);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Unable to run analysis. Please try again.';
      setAnalysisError(message);
    } finally {
      setAnalysisLoading(false);
    }
  };

  useEffect(() => {
    let cancelled = false;

    const loadControlFlow = async () => {
      setCfgLoading(true);
      setCfgError(null);
      try {
        console.log('[App] Loading control flow diagram...');
        const diagram = await fetchControlFlow();
        console.log('[App] Control flow diagram loaded:', diagram);
        if (cancelled) return;
        
        // Ensure nodes have positions (React Flow requirement)
        // If nodes don't have positions, apply layout function
        const nodesWithPositions = diagram.nodes.map((node) => {
          // If node already has a position, use it; otherwise layout will add one
          if (!node.position || typeof node.position.x !== 'number' || typeof node.position.y !== 'number') {
            // Return node with temporary position - layoutCfgNodes will fix it
            return {
              ...node,
              position: node.position || { x: 0, y: 0 },
            };
          }
          return node;
        });
        
        // Apply layout to ensure all nodes have proper positions
        const laidOutNodes = layoutCfgNodes(nodesWithPositions, diagram.edges);
        
        setNodes(laidOutNodes);
        setEdges(diagram.edges);
        setTaskDescription(diagram.task_description);
        if (laidOutNodes.length > 0) {
          setActiveNodeId(laidOutNodes[0].id);
        }
      } catch (error) {
        console.error('[App] Error loading control flow:', error);
        if (cancelled) return;
        const message =
          error instanceof Error
            ? error.message
            : 'Unable to load control-flow diagram.';
        setCfgError(message);
      } finally {
        if (!cancelled) {
          setCfgLoading(false);
        }
      }
    };

    void loadControlFlow();

    return () => {
      cancelled = true;
    };
  }, []);

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
            suite={suite}
            testCase={testCase}
            analysis={analysis}
            attempts={attempts}
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
            <div className="absolute right-4 top-4 z-50 flex gap-2">
              <button
                className="inline-flex items-center gap-1 rounded-md border border-border bg-card px-3 py-1.5 text-sm font-medium shadow-sm hover:bg-accent disabled:cursor-not-allowed disabled:opacity-70"
                onClick={runAnalysis}
                disabled={cfgLoading || analysisLoading}
              >
                {analysisLoading ? 'Running analysis…' : 'Run analysis'}
              </button>
            </div>

            {cfgError && (
              <div className="h-full w-full flex items-center justify-center">
                <div className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
                  {cfgError}
                </div>
              </div>
            )}
            {!cfgError && nodes.length === 0 && (
              <div className="h-full w-full flex items-center justify-center text-sm text-muted-foreground">
                {cfgLoading ? 'Loading control-flow diagram…' : 'No diagram available.'}
              </div>
            )}
            {!cfgError && nodes.length > 0 && (
              <CfgCanvas
                initialNodes={nodes}
                initialEdges={edges}
                activeNodeId={activeNodeId}
                onNodeClick={handleNodeClick}
                problems={problems}
              />
            )}
            {analysisError && (
              <div className="absolute right-4 bottom-4 bg-destructive/10 border border-destructive/40 text-destructive text-xs px-3 py-2 rounded-md shadow-sm">
                {analysisError}
              </div>
            )}
          </div>
        </ResizablePanel>
      </ResizablePanelGroup>
    </div>
  );
}

export default App;
