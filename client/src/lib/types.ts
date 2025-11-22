export type RuntimeValue = 
  | string 
  | number 
  | boolean 
  | null 
  | undefined 
  | RuntimeValue[] 
  | { [key: string]: RuntimeValue };

export interface VariableState {
  [key: string]: RuntimeValue;
}

export interface RuntimeStep {
  id: string;
  blockId: string;
  blockName: string;
  codeSnippet: string;
  before: VariableState;
  after: VariableState;
  status: 'succeeded' | 'failed' | 'pending';
  error?: string; // Error message if failed
}

export interface Problem {
  id: string;
  blockId: string;
  stepId: string; // Which execution step failed
  description: string;
  severity: 'error' | 'warning';
}

export type NodeStatus = 'pending' | 'failed' | 'succeeded';

export interface CfgNodeData extends Record<string, unknown> {
  blockId: string;
  blockName: string;
  codeSnippet: string;
  status: NodeStatus;
  file?: string;
  lineStart?: number;
  lineEnd?: number;
  executionCount?: number; // How many times this block ran
}

// Global state interface (conceptual)
export interface DebuggerState {
  activeNodeId: string | null;
  activeStepId: string | null;
  steps: RuntimeStep[];
  problems: Problem[];
  isSidebarOpen: boolean;
}
