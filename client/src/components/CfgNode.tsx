import React, { memo, useMemo } from 'react';
import { Handle, Position, type Node, type NodeProps, useNodeConnections } from '@xyflow/react';
import type { CfgNodeData } from '@/lib/types';
import { cn, getFileIcon } from '@/lib/utils';
import { CheckCircle2, XCircle, Loader2, AlertTriangle } from 'lucide-react';

// NodeProps expects a Node type; we define one with our custom data
type CfgFlowNode = Node<CfgNodeData>;

const FileIconComponent = ({ fileName, className }: { fileName?: string; className?: string }) => {
  const IconComponent = useMemo(() => getFileIcon(fileName), [fileName]);
  return React.createElement(IconComponent, { className });
};

const StatusPill = ({ status }: { status: CfgNodeData['status'] }) => {
  switch (status) {
    case 'succeeded':
      return (
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 border border-green-200 text-[10px] font-medium">
          <CheckCircle2 className="h-3 w-3" />
          <span>Succeeded</span>
        </div>
      );
    case 'failed':
      return (
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-100 text-red-700 border border-red-200 text-[10px] font-medium">
          <XCircle className="h-3 w-3" />
          <span>Failed</span>
        </div>
      );
    case 'pending':
      return (
        <div className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 border border-yellow-200 text-[10px] font-medium">
          <Loader2 className="h-3 w-3 animate-spin" />
          <span>Pending</span>
        </div>
      );
  }
};

export const CfgNode = memo(({ data, selected, isConnectable }: NodeProps<CfgFlowNode>) => {
  const nodeData = data;
  const [showMetadata, setShowMetadata] = React.useState(false);
  const [showError, setShowError] = React.useState(false);

  const targetConnections = useNodeConnections({ handleType: 'target' });
  const sourceConnections = useNodeConnections({ handleType: 'source' });

  return (
    <div 
      className={cn(
        "relative min-w-[200px] bg-card rounded-lg border shadow-sm transition-all duration-200",
        selected ? "border-primary ring-2 ring-primary/20 shadow-md" : "border-border hover:border-primary/50",
        nodeData.status === 'failed' && "border-red-300 bg-red-50/10"
      )}
      onMouseEnter={() => setShowMetadata(true)}
      onMouseLeave={() => setShowMetadata(false)}
    >
      <Handle 
        type="target" 
        position={Position.Top} 
        className={cn("bg-muted-foreground!", !targetConnections.length && "invisible")} 
        isConnectable={isConnectable} 
      />
      
      {/* Metadata Tooltip */}
      {showMetadata && nodeData.file && (
        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 z-50 w-max px-3 py-1.5 bg-popover text-popover-foreground text-xs rounded shadow-md border border-border animate-in fade-in zoom-in-95 duration-100">
          <div className="flex items-center gap-2">
            <FileIconComponent fileName={nodeData.file} className="h-3 w-3 text-muted-foreground" />
            <span className="font-mono">{nodeData.file}</span>
            {nodeData.lineStart !== undefined && nodeData.lineEnd !== undefined && (
              <span className="text-muted-foreground">
                L{nodeData.lineStart}-{nodeData.lineEnd}
              </span>
            )}
          </div>
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border/50 bg-muted/10 rounded-t-lg">
        <span className="text-xs font-bold text-foreground">{nodeData.blockName}</span>
        <StatusPill status={nodeData.status} />
      </div>

      {/* Body */}
      <div className="p-3 font-mono text-xs bg-background/50 rounded-b-lg overflow-hidden">
         <pre className="whitespace-pre-wrap wrap-break-word text-foreground/90">
           {nodeData.codeSnippet}
         </pre>
      </div>

      {/* Error Affordance */}
      {nodeData.status === 'failed' && (
        <div className="absolute -right-2 -bottom-2">
           <button 
             className="bg-red-500 text-white p-1.5 rounded-full shadow-md hover:bg-red-600 transition-colors"
             onClick={(e) => {
               e.stopPropagation(); // Prevent node selection if just checking error
               setShowError(!showError);
             }}
           >
             <AlertTriangle className="h-3 w-3" />
           </button>
           
           {showError && (
             <div className="absolute right-0 top-8 w-64 p-3 bg-popover text-popover-foreground rounded-md border border-red-200 shadow-xl z-50 text-xs">
                <div className="font-semibold mb-1 text-red-600">Error Analysis</div>
                <p>
                  {/* In a real app, this would come from data.error or matched problem */}
                  This block produced an incorrect value for 'cnt'. Expected increment of 1, got 2.
                </p>
             </div>
           )}
        </div>
      )}

      <Handle 
        type="source" 
        position={Position.Bottom} 
        className={cn("bg-muted-foreground!", !sourceConnections.length && "invisible")} 
        isConnectable={isConnectable} 
      />
    </div>
  );
});
