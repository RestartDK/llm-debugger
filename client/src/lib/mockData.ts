import type { RuntimeStep, Problem, CfgNodeData } from './types';
import type { Edge, Node } from '@xyflow/react';

export const mockSteps: RuntimeStep[] = [
  {
    id: 'step-1',
    blockId: 'block-A',
    blockName: 'Block A',
    codeSnippet: "cnt = 0; s = 'LLM'",
    before: { s: 'LLM', cnt: undefined },
    after: { s: 'LLM', cnt: 0 },
    status: 'succeeded'
  },
  {
    id: 'step-2',
    blockId: 'block-B',
    blockName: 'Block B',
    codeSnippet: "for c in s:",
    before: { cnt: 0, s: 'LLM' },
    after: { cnt: 0, c: 'L' },
    status: 'succeeded'
  },
  {
    id: 'step-3',
    blockId: 'block-C',
    blockName: 'Block C',
    codeSnippet: "cnt += 2",
    before: { cnt: 0, c: 'L' },
    after: { cnt: 2, c: 'L' },
    status: 'failed',
    error: "cnt increments by 2, should be 1"
  },
  {
    id: 'step-4',
    blockId: 'block-B',
    blockName: 'Block B',
    codeSnippet: "for c in s:",
    before: { cnt: 2, c: 'L' },
    after: { cnt: 2, c: 'L' }, // 2nd iteration L
    status: 'succeeded'
  },
  {
    id: 'step-5',
    blockId: 'block-C',
    blockName: 'Block C',
    codeSnippet: "cnt += 2",
    before: { cnt: 2, c: 'L' },
    after: { cnt: 4, c: 'L' },
    status: 'failed',
    error: "cnt increments by 2, should be 1"
  }
];

export const mockProblems: Problem[] = [
  {
    id: 'prob-1',
    blockId: 'block-C',
    stepId: 'step-3',
    description: 'cnt increments by 2, should be 1',
    severity: 'error'
  },
  {
    id: 'prob-2',
    blockId: 'block-C',
    stepId: 'step-5',
    description: 'cnt increments by 2, should be 1',
    severity: 'error'
  }
];

export const initialNodes: Node<CfgNodeData>[] = [
  {
    id: 'block-A',
    type: 'cfgNode',
    position: { x: 250, y: 0 },
    data: {
      blockId: 'block-A',
      blockName: 'Block A',
      codeSnippet: "cnt = 0; s = 'LLM'",
      status: 'succeeded',
      file: 'counter.py',
      lineStart: 10,
      lineEnd: 10
    }
  },
  {
    id: 'block-B',
    type: 'cfgNode',
    position: { x: 250, y: 150 },
    data: {
      blockId: 'block-B',
      blockName: 'Block B',
      codeSnippet: "for c in s:",
      status: 'succeeded',
      file: 'counter.py',
      lineStart: 12,
      lineEnd: 12
    }
  },
  {
    id: 'block-C',
    type: 'cfgNode',
    position: { x: 100, y: 300 },
    data: {
      blockId: 'block-C',
      blockName: 'Block C',
      codeSnippet: "cnt += 2",
      status: 'failed',
      file: 'counter.py',
      lineStart: 13,
      lineEnd: 13
    }
  },
    {
    id: 'block-D',
    type: 'cfgNode',
    position: { x: 400, y: 300 },
    data: {
      blockId: 'block-D',
      blockName: 'Block D',
      codeSnippet: "pass",
      status: 'pending',
      file: 'counter.py',
      lineStart: 15,
      lineEnd: 15
    }
  }
];

export const initialEdges: Edge[] = [
  { id: 'e1-2', source: 'block-A', target: 'block-B' },
  { id: 'e2-3', source: 'block-B', target: 'block-C' },
  { id: 'e2-4', source: 'block-B', target: 'block-D' },
  { id: 'e3-2', source: 'block-C', target: 'block-B' },
];

