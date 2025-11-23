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
  type ReactFlowInstance,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import { CfgNode } from './CfgNode';
import type { CfgNodeData, Problem } from '@/lib/types';
import { layoutCfgNodes } from '@/lib/utils';

// Create node types with access to problems
const createNodeTypes = (problems: Problem[]): NodeTypes => ({
  cfgNode: (props) => <CfgNode {...props} problems={problems} />,
});

const buildEdgeKey = (edge: Edge) => edge.id ?? `${edge.source}->${edge.target}`;

const mergeNodesById = (current: Node<CfgNodeData>[], incoming: Node<CfgNodeData>[]) => {
  if (!incoming.length) {
    return current;
  }

  const map = new Map(current.map((node) => [node.id, node]));

  incoming.forEach((node) => {
    const existing = map.get(node.id);
    if (existing) {
      map.set(node.id, {
        ...existing,
        ...node,
        data: {
          ...existing.data,
          ...node.data,
        },
      });
    } else {
      map.set(node.id, node);
    }
  });

  return Array.from(map.values());
};

const mergeEdgesById = (current: Edge[], incoming: Edge[]) => {
  if (!incoming.length) {
    return current;
  }

  const map = new Map(current.map((edge) => [buildEdgeKey(edge), edge]));

  incoming.forEach((edge) => {
    map.set(buildEdgeKey(edge), edge);
  });

  return Array.from(map.values());
};

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
  const activeNodeIdRef = React.useRef<string | null>(activeNodeId);
  const [reactFlowInstance, setReactFlowInstance] = React.useState<ReactFlowInstance<Node<CfgNodeData>, Edge> | null>(null);
  const graphNodesRef = React.useRef<Node<CfgNodeData>[]>(initialNodes);
  const graphEdgesRef = React.useRef<Edge[]>(initialEdges);
  const measuredDimensionsRef = React.useRef<Map<string, { width: number; height: number }>>(new Map());

  React.useEffect(() => {
    activeNodeIdRef.current = activeNodeId;
  }, [activeNodeId]);

  // Allow props to reset layout when backend data changes.
  React.useEffect(() => {
    const prevNodes = graphNodesRef.current;
    const prevIds = new Set(prevNodes.map((node) => node.id));
    const sharesIds =
      prevNodes.length > 0 &&
      initialNodes.length > 0 &&
      initialNodes.some((node) => prevIds.has(node.id));
    const shouldReplaceGraph = prevNodes.length === 0 || initialNodes.length === 0 || !sharesIds;

    if (shouldReplaceGraph) {
      graphNodesRef.current = initialNodes.slice();
      graphEdgesRef.current = initialEdges.slice();
    } else {
      graphNodesRef.current = mergeNodesById(graphNodesRef.current, initialNodes);
      graphEdgesRef.current = mergeEdgesById(graphEdgesRef.current, initialEdges);
    }

    const laidOut = layoutCfgNodes(graphNodesRef.current, graphEdgesRef.current).map((node) => ({
      ...node,
      selected: node.id === activeNodeIdRef.current,
    }));
    setNodes(laidOut);
    setEdges(graphEdgesRef.current);
    if (reactFlowInstance) {
      requestAnimationFrame(() => {
        reactFlowInstance.fitView({ padding: 0.2, duration: 400 });
      });
    }
  }, [initialNodes, initialEdges, setNodes, setEdges, reactFlowInstance]);

  React.useEffect(() => {
    if (!reactFlowInstance) {
      return;
    }

    const measuredNodes = reactFlowInstance.getNodes();
    let hasNewMeasurements = false;

    measuredNodes.forEach((measuredNode) => {
      if (!measuredNode.measured) {
        return;
      }
      const width = measuredNode.measured.width;
      const height = measuredNode.measured.height;
      if (width == null || height == null) {
        return;
      }
      const prev = measuredDimensionsRef.current.get(measuredNode.id);
      if (!prev || prev.width !== width || prev.height !== height) {
        measuredDimensionsRef.current.set(measuredNode.id, { width, height });
        hasNewMeasurements = true;
      }
    });

    if (!hasNewMeasurements) {
      return;
    }

    graphNodesRef.current = graphNodesRef.current.map((node) => {
      const dimensions = measuredDimensionsRef.current.get(node.id);
      if (!dimensions) {
        return node;
      }
      return {
        ...node,
        width: dimensions.width,
        height: dimensions.height,
      };
    });

    const reLaidOut = layoutCfgNodes(graphNodesRef.current, graphEdgesRef.current).map((node) => ({
      ...node,
      selected: node.id === activeNodeIdRef.current,
    }));

    setNodes(reLaidOut);
    setEdges(graphEdgesRef.current);
    requestAnimationFrame(() => {
      reactFlowInstance.fitView({ padding: 0.2, duration: 400 });
    });
  }, [nodes, reactFlowInstance, setNodes, setEdges]);
  
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
      <ReactFlow<Node<CfgNodeData>, Edge>
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        nodeTypes={nodeTypes}
        fitView
        onInit={setReactFlowInstance}
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

