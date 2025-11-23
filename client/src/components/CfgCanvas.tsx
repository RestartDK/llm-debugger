import React from 'react';
import {
  ReactFlow,
  Controls,
  Background,
  useNodesState,
  useEdgesState,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { CfgNode } from './CfgNode';
import type { CfgNodeData, Problem } from '@/lib/types';

// Create node types with access to problems
const createNodeTypes = (problems: Problem[]): NodeTypes => ({
  cfgNode: (props) => <CfgNode {...props} problems={problems} />,
});

interface CfgCanvasProps {
  initialNodes: Node<CfgNodeData>[];
  initialEdges: Edge[];
  activeNodeId: string | null;
  onNodeClick: (nodeId: string) => void;
  problems?: Problem[];
}

export const CfgCanvas: React.FC<CfgCanvasProps> = ({
  initialNodes,
  initialEdges,
  activeNodeId,
  onNodeClick,
  problems = [],
}) => {
  // We manage nodes/edges locally for layout, but selection is driven by props + local click
  const [nodes, setNodes, onNodesChange] = useNodesState<Node<CfgNodeData>>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(initialEdges);

  // Allow props to reset layout when backend data changes.
  React.useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  React.useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);
  
  // Create node types with problems
  const nodeTypes = React.useMemo(() => createNodeTypes(problems), [problems]);

  // Sync selection from props
  React.useEffect(() => {
    setNodes((nds) =>
      nds.map((node) => ({
        ...node,
        selected: node.id === activeNodeId,
      }))
    );
  }, [activeNodeId, setNodes]);

  return (
    <div className="h-full w-full bg-background">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        onNodeClick={(_, node) => onNodeClick(node.id)}
        nodesConnectable={false}
        edgesReconnectable={false}
      >
        <Background color="#888" gap={16} />
        <Controls className="bg-card border border-border fill-foreground" />
      </ReactFlow>
    </div>
  );
};

