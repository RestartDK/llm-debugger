import type { RuntimeStep, Problem, CfgNodeData } from './types';
import type { Edge, Node } from '@xyflow/react';

// Complex demo: Processing student scores with validation, filtering, and aggregation
// Simulates a function that processes scores, validates them, filters by threshold,
// and aggregates results with early exit conditions

export const mockSteps: RuntimeStep[] = [
  // Entry: Initialize variables
  {
    id: 'step-1',
    blockId: 'block-entry',
    blockName: 'Entry',
    codeSnippet: "scores = [85, 92, -5, 78, 95]; total = 0; count = 0; threshold = 80",
    before: {},
    after: { scores: [85, 92, -5, 78, 95], total: 0, count: 0, threshold: 80 },
    status: 'succeeded'
  },
  // Loop: Iterate over scores
  {
    id: 'step-2',
    blockId: 'block-loop',
    blockName: 'Loop',
    codeSnippet: "for score in scores:",
    before: { scores: [85, 92, -5, 78, 95], total: 0, count: 0, threshold: 80 },
    after: { scores: [85, 92, -5, 78, 95], total: 0, count: 0, threshold: 80, score: 85 },
    status: 'succeeded'
  },
  // Validation: Check if score is valid
  {
    id: 'step-3',
    blockId: 'block-validate',
    blockName: 'Validate',
    codeSnippet: "if score < 0 or score > 100:",
    before: { score: 85, total: 0, count: 0, threshold: 80 },
    after: { score: 85, total: 0, count: 0, threshold: 80 },
    status: 'succeeded'
  },
  // Filter: Check threshold (first iteration, score=85)
  {
    id: 'step-4',
    blockId: 'block-filter',
    blockName: 'Filter',
    codeSnippet: "if score >= threshold:",
    before: { score: 85, total: 0, count: 0, threshold: 80 },
    after: { score: 85, total: 0, count: 0, threshold: 80 },
    status: 'succeeded'
  },
  // Aggregate: Update totals
  {
    id: 'step-5',
    blockId: 'block-aggregate',
    blockName: 'Aggregate',
    codeSnippet: "total += score; count += 1",
    before: { score: 85, total: 0, count: 0 },
    after: { score: 85, total: 85, count: 1 },
    status: 'succeeded'
  },
  // Early exit check
  {
    id: 'step-6',
    blockId: 'block-exit-check',
    blockName: 'Exit Check',
    codeSnippet: "if count >= 3:",
    before: { total: 85, count: 1 },
    after: { total: 85, count: 1 },
    status: 'succeeded'
  },
  // Loop: Second iteration (score=92)
  {
    id: 'step-7',
    blockId: 'block-loop',
    blockName: 'Loop',
    codeSnippet: "for score in scores:",
    before: { total: 85, count: 1, score: 85 },
    after: { total: 85, count: 1, score: 92 },
    status: 'succeeded'
  },
  // Validation: Second iteration
  {
    id: 'step-8',
    blockId: 'block-validate',
    blockName: 'Validate',
    codeSnippet: "if score < 0 or score > 100:",
    before: { score: 92, total: 85, count: 1 },
    after: { score: 92, total: 85, count: 1 },
    status: 'succeeded'
  },
  // Filter: Second iteration
  {
    id: 'step-9',
    blockId: 'block-filter',
    blockName: 'Filter',
    codeSnippet: "if score >= threshold:",
    before: { score: 92, total: 85, count: 1, threshold: 80 },
    after: { score: 92, total: 85, count: 1, threshold: 80 },
    status: 'succeeded'
  },
  // Aggregate: Second iteration
  {
    id: 'step-10',
    blockId: 'block-aggregate',
    blockName: 'Aggregate',
    codeSnippet: "total += score; count += 1",
    before: { score: 92, total: 85, count: 1 },
    after: { score: 92, total: 177, count: 2 },
    status: 'succeeded'
  },
  // Exit check: Second iteration
  {
    id: 'step-11',
    blockId: 'block-exit-check',
    blockName: 'Exit Check',
    codeSnippet: "if count >= 3:",
    before: { total: 177, count: 2 },
    after: { total: 177, count: 2 },
    status: 'succeeded'
  },
  // Loop: Third iteration (score=-5, invalid)
  {
    id: 'step-12',
    blockId: 'block-loop',
    blockName: 'Loop',
    codeSnippet: "for score in scores:",
    before: { total: 177, count: 2, score: 92 },
    after: { total: 177, count: 2, score: -5 },
    status: 'succeeded'
  },
  // Validation: Third iteration - invalid score detected
  {
    id: 'step-13',
    blockId: 'block-validate',
    blockName: 'Validate',
    codeSnippet: "if score < 0 or score > 100:",
    before: { score: -5, total: 177, count: 2 },
    after: { score: -5, total: 177, count: 2 },
    status: 'succeeded'
  },
  // Skip invalid: Handle invalid score
  {
    id: 'step-14',
    blockId: 'block-skip-invalid',
    blockName: 'Skip Invalid',
    codeSnippet: "continue",
    before: { score: -5, total: 177, count: 2 },
    after: { score: -5, total: 177, count: 2 },
    status: 'succeeded'
  },
  // Loop: Fourth iteration (score=78, below threshold)
  {
    id: 'step-15',
    blockId: 'block-loop',
    blockName: 'Loop',
    codeSnippet: "for score in scores:",
    before: { total: 177, count: 2, score: -5 },
    after: { total: 177, count: 2, score: 78 },
    status: 'succeeded'
  },
  // Validation: Fourth iteration
  {
    id: 'step-16',
    blockId: 'block-validate',
    blockName: 'Validate',
    codeSnippet: "if score < 0 or score > 100:",
    before: { score: 78, total: 177, count: 2 },
    after: { score: 78, total: 177, count: 2 },
    status: 'succeeded'
  },
  // Filter: Fourth iteration - below threshold
  {
    id: 'step-17',
    blockId: 'block-filter',
    blockName: 'Filter',
    codeSnippet: "if score >= threshold:",
    before: { score: 78, total: 177, count: 2, threshold: 80 },
    after: { score: 78, total: 177, count: 2, threshold: 80 },
    status: 'succeeded'
  },
  // Loop: Fifth iteration (score=95)
  {
    id: 'step-18',
    blockId: 'block-loop',
    blockName: 'Loop',
    codeSnippet: "for score in scores:",
    before: { total: 177, count: 2, score: 78 },
    after: { total: 177, count: 2, score: 95 },
    status: 'succeeded'
  },
  // Validation: Fifth iteration
  {
    id: 'step-19',
    blockId: 'block-validate',
    blockName: 'Validate',
    codeSnippet: "if score < 0 or score > 100:",
    before: { score: 95, total: 177, count: 2 },
    after: { score: 95, total: 177, count: 2 },
    status: 'succeeded'
  },
  // Filter: Fifth iteration
  {
    id: 'step-20',
    blockId: 'block-filter',
    blockName: 'Filter',
    codeSnippet: "if score >= threshold:",
    before: { score: 95, total: 177, count: 2, threshold: 80 },
    after: { score: 95, total: 177, count: 2, threshold: 80 },
    status: 'succeeded'
  },
  // Aggregate: Fifth iteration - BUG: should increment by 1, but increments by 2
  {
    id: 'step-21',
    blockId: 'block-aggregate',
    blockName: 'Aggregate',
    codeSnippet: "total += score; count += 2",
    before: { score: 95, total: 177, count: 2 },
    after: { score: 95, total: 272, count: 4 },
    status: 'failed',
    error: "count increments by 2, should increment by 1"
  },
  // Exit check: Fifth iteration - triggers early exit
  {
    id: 'step-22',
    blockId: 'block-exit-check',
    blockName: 'Exit Check',
    codeSnippet: "if count >= 3:",
    before: { total: 272, count: 4 },
    after: { total: 272, count: 4 },
    status: 'succeeded'
  },
  // Early exit: Break from loop
  {
    id: 'step-23',
    blockId: 'block-early-exit',
    blockName: 'Early Exit',
    codeSnippet: "break",
    before: { total: 272, count: 4 },
    after: { total: 272, count: 4 },
    status: 'succeeded'
  },
  // Return: Calculate average
  {
    id: 'step-24',
    blockId: 'block-return',
    blockName: 'Return',
    codeSnippet: "return total / count if count > 0 else 0",
    before: { total: 272, count: 4 },
    after: { total: 272, count: 4, result: 68 },
    status: 'succeeded'
  }
];

export const mockProblems: Problem[] = [
  {
    id: 'prob-1',
    blockId: 'block-aggregate',
    stepId: 'step-21',
    description: 'count increments by 2, should increment by 1',
    severity: 'error'
  },
  {
    id: 'prob-2',
    blockId: 'block-return',
    stepId: 'step-24',
    description: 'Average calculation incorrect: count is 4 but should be 3 (bug in aggregate)',
    severity: 'warning'
  }
];

export const initialNodes: Node<CfgNodeData>[] = [
  {
    id: 'block-entry',
    type: 'cfgNode',
    position: { x: 400, y: 0 },
    data: {
      blockId: 'block-entry',
      blockName: 'Entry',
      codeSnippet: "scores = [85, 92, -5, 78, 95]; total = 0; count = 0; threshold = 80",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 5,
      lineEnd: 5,
      executionCount: 1
    }
  },
  {
    id: 'block-loop',
    type: 'cfgNode',
    position: { x: 400, y: 120 },
    data: {
      blockId: 'block-loop',
      blockName: 'Loop',
      codeSnippet: "for score in scores:",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 7,
      lineEnd: 7,
      executionCount: 5
    }
  },
  {
    id: 'block-validate',
    type: 'cfgNode',
    position: { x: 400, y: 240 },
    data: {
      blockId: 'block-validate',
      blockName: 'Validate',
      codeSnippet: "if score < 0 or score > 100:",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 8,
      lineEnd: 8,
      executionCount: 5
    }
  },
  {
    id: 'block-skip-invalid',
    type: 'cfgNode',
    position: { x: 200, y: 360 },
    data: {
      blockId: 'block-skip-invalid',
      blockName: 'Skip Invalid',
      codeSnippet: "continue",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 9,
      lineEnd: 9,
      executionCount: 1
    }
  },
  {
    id: 'block-filter',
    type: 'cfgNode',
    position: { x: 600, y: 360 },
    data: {
      blockId: 'block-filter',
      blockName: 'Filter',
      codeSnippet: "if score >= threshold:",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 11,
      lineEnd: 11,
      executionCount: 4
    }
  },
  {
    id: 'block-aggregate',
    type: 'cfgNode',
    position: { x: 600, y: 480 },
    data: {
      blockId: 'block-aggregate',
      blockName: 'Aggregate',
      codeSnippet: "total += score; count += 2",
      status: 'failed',
      file: 'score_processor.py',
      lineStart: 12,
      lineEnd: 13,
      executionCount: 3
    }
  },
  {
    id: 'block-exit-check',
    type: 'cfgNode',
    position: { x: 600, y: 600 },
    data: {
      blockId: 'block-exit-check',
      blockName: 'Exit Check',
      codeSnippet: "if count >= 3:",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 14,
      lineEnd: 14,
      executionCount: 3
    }
  },
  {
    id: 'block-early-exit',
    type: 'cfgNode',
    position: { x: 800, y: 720 },
    data: {
      blockId: 'block-early-exit',
      blockName: 'Early Exit',
      codeSnippet: "break",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 15,
      lineEnd: 15,
      executionCount: 1
    }
  },
  {
    id: 'block-return',
    type: 'cfgNode',
    position: { x: 400, y: 840 },
    data: {
      blockId: 'block-return',
      blockName: 'Return',
      codeSnippet: "return total / count if count > 0 else 0",
      status: 'succeeded',
      file: 'score_processor.py',
      lineStart: 18,
      lineEnd: 18,
      executionCount: 1
    }
  }
];

export const initialEdges: Edge[] = [
  // Entry to loop
  { id: 'e-entry-loop', source: 'block-entry', target: 'block-loop' },
  // Loop to validate
  { id: 'e-loop-validate', source: 'block-loop', target: 'block-validate' },
  // Validate branches: invalid -> skip -> back to loop
  { id: 'e-validate-skip', source: 'block-validate', target: 'block-skip-invalid' },
  { id: 'e-skip-loop', source: 'block-skip-invalid', target: 'block-loop' },
  // Validate branches: valid -> filter
  { id: 'e-validate-filter', source: 'block-validate', target: 'block-filter' },
  // Filter branches: below threshold -> back to loop
  { id: 'e-filter-loop', source: 'block-filter', target: 'block-loop' },
  // Filter branches: above threshold -> aggregate
  { id: 'e-filter-aggregate', source: 'block-filter', target: 'block-aggregate' },
  // Aggregate to exit check
  { id: 'e-aggregate-exit-check', source: 'block-aggregate', target: 'block-exit-check' },
  // Exit check branches: count < 3 -> back to loop
  { id: 'e-exit-check-loop', source: 'block-exit-check', target: 'block-loop' },
  // Exit check branches: count >= 3 -> early exit
  { id: 'e-exit-check-early', source: 'block-exit-check', target: 'block-early-exit' },
  // Early exit to return
  { id: 'e-early-return', source: 'block-early-exit', target: 'block-return' },
  // Loop end (when exhausted) to return
  { id: 'e-loop-return', source: 'block-loop', target: 'block-return' }
];

