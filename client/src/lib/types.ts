import type { Edge, Node } from '@xyflow/react';

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

export interface ControlFlowResponse {
  nodes: Node<CfgNodeData>[];
  edges: Edge[];
  task_description?: string;
}

export interface TestCase {
  name: string;
  description: string;
  input: string;
  expected_output: string;
  notes?: string | null;
}

export interface TestSuite {
  target_function: string;
  summary: string;
  test_style: string;
  tests: TestCase[];
}

export interface FailedTest {
  name: string;
  input: string;
  expected: string;
  actual: string;
  notes?: string | null;
}

export interface Analysis {
  task_description: string;
  failed_test?: FailedTest;
  assessments?: unknown[];
}

export interface DebuggerPayload extends ControlFlowResponse {
  suite?: TestSuite;
  test_case?: TestCase;
  trace: Record<string, unknown>[];
  steps: RuntimeStep[];
  problems: Problem[];
  analysis?: Analysis;
}

export interface ExecuteTestCasesRequest {
  task_description?: string;
  sources?: { file_path: string; code: string }[];
  blocks?: Array<{
    block_id: string;
    file_path: string;
    start_line: number;
    end_line: number;
  }>;
}
