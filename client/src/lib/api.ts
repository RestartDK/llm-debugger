import type {
  ControlFlowResponse,
  DebuggerPayload,
  ExecuteTestCasesRequest,
  CfgNodeData,
} from './types';
import type { Node, Edge } from '@xyflow/react';

type Json = Record<string, unknown>;

// API response format (what comes from backend)
interface ApiNode {
  id: string;
  code_chunk: string;
  explanation?: string;
  relationships?: string;
  filename?: string;
  line_range?: string; // Format: "15-24" or "20-25"
}

interface ApiEdge {
  id: string;
  from_node: string;
  to_node: string;
  relationship_type?: string;
}

interface ApiControlFlowResponse {
  nodes: ApiNode[];
  edges: ApiEdge[];
  task_description?: string;
}

class HttpError extends Error {
  status: number;
  payload?: Json;

  constructor(message: string, status: number, payload?: Json) {
    super(message);
    this.status = status;
    this.payload = payload;
  }
}

const normalizeBaseUrl = (url: string | undefined): string => {
  if (!url) {
    // Fall back to relative URLs; configure VITE_API_BASE_URL for explicit host/port.
    return '';
  }
  return url.endsWith('/') ? url.slice(0, -1) : url;
};

const API_BASE_URL = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL);

const buildUrl = (path: string): string => {
  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }
  const normalizedPath = path.startsWith('/') ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

async function request<TResponse>(
  path: string,
  options: RequestInit = {},
): Promise<TResponse> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  const url = buildUrl(path);
  console.log('[API] Making request to:', url);

  try {
    const response = await fetch(url, {
      ...options,
      headers,
    });

    console.log('[API] Response status:', response.status, response.statusText);
    console.log('[API] Response headers:', Object.fromEntries(response.headers.entries()));

    const isJsonResponse =
      response.headers.get('content-type')?.includes('application/json');

    const payload = isJsonResponse ? await response.json() : undefined;

    if (!response.ok) {
      console.error('[API] Request failed:', {
        url,
        status: response.status,
        payload,
      });
      throw new HttpError(
        payload?.message?.toString() ||
          `Request to ${path} failed with status ${response.status}`,
        response.status,
        payload,
      );
    }

    console.log('[API] Request successful:', url);
    return payload as TResponse;
  } catch (error) {
    console.error('[API] Request error:', {
      url,
      error: error instanceof Error ? error.message : String(error),
      stack: error instanceof Error ? error.stack : undefined,
    });
    throw error;
  }
}

/**
 * Transform API response format to React Flow format
 */
function transformApiResponseToReactFlow(
  apiResponse: ApiControlFlowResponse,
): ControlFlowResponse {
  // Transform nodes from API format to React Flow format
  const nodes: Node<CfgNodeData>[] = apiResponse.nodes.map((apiNode) => {
    // Parse line_range (format: "15-24" or "20-25")
    let lineStart: number | undefined;
    let lineEnd: number | undefined;
    if (apiNode.line_range) {
      const parts = apiNode.line_range.split('-');
      if (parts.length === 2) {
        lineStart = parseInt(parts[0], 10);
        lineEnd = parseInt(parts[1], 10);
        if (isNaN(lineStart)) lineStart = undefined;
        if (isNaN(lineEnd)) lineEnd = undefined;
      }
    }

    // Extract block name from id (use id as blockName)
    const blockName = apiNode.id;

    const nodeData: CfgNodeData = {
      blockId: apiNode.id,
      blockName: blockName,
      codeSnippet: apiNode.code_chunk,
      status: 'pending', // Default status
      file: apiNode.filename,
      lineStart,
      lineEnd,
    };

    return {
      id: apiNode.id,
      type: 'cfgNode', // React Flow node type
      position: { x: 0, y: 0 }, // Temporary position, will be set by layout function
      data: nodeData,
    };
  });

  // Transform edges from API format to React Flow format
  const edges: Edge[] = apiResponse.edges.map((apiEdge) => ({
    id: apiEdge.id,
    source: apiEdge.from_node,
    target: apiEdge.to_node,
    type: 'smoothstep', // React Flow edge type
    animated: false,
    label: apiEdge.relationship_type, // Optional: show relationship type on edge
  }));

  return {
    nodes,
    edges,
    task_description: apiResponse.task_description,
  };
}

export const fetchControlFlow = async (): Promise<ControlFlowResponse> => {
  const apiResponse = await request<ApiControlFlowResponse>(
    '/get_control_flow_diagram',
  );
  console.log('[API] Raw API response:', apiResponse);
  const transformed = transformApiResponseToReactFlow(apiResponse);
  console.log('[API] Transformed response:', transformed);
  return transformed;
};

/**
 * Convert React Flow nodes to backend blocks format
 */
export function convertNodesToBlocks(
  nodes: Node<CfgNodeData>[],
): Array<{
  block_id: string;
  file_path: string;
  start_line: number;
  end_line: number;
}> {
  return nodes
    .filter(
      (node) =>
        node.data.file &&
        node.data.lineStart !== undefined &&
        node.data.lineEnd !== undefined,
    )
    .map((node) => ({
      block_id: node.id,
      file_path: node.data.file || '',
      start_line: node.data.lineStart || 0,
      end_line: node.data.lineEnd || 0,
    }));
}

/**
 * Extract sources from nodes by grouping code snippets by file
 */
export function extractSourcesFromNodes(
  nodes: Node<CfgNodeData>[],
): Array<{ file_path: string; code: string }> {
  // Group nodes by file
  const fileMap = new Map<string, Node<CfgNodeData>[]>();

  nodes.forEach((node) => {
    if (node.data.file) {
      const file = node.data.file;
      if (!fileMap.has(file)) {
        fileMap.set(file, []);
      }
      fileMap.get(file)!.push(node);
    }
  });

  // Combine code snippets for each file
  const sources: Array<{ file_path: string; code: string }> = [];

  fileMap.forEach((fileNodes, filePath) => {
    // Sort nodes by lineStart to maintain order
    const sortedNodes = [...fileNodes].sort(
      (a, b) => (a.data.lineStart || 0) - (b.data.lineStart || 0),
    );

    // Combine code snippets - for now, just join them with newlines
    // In a more sophisticated implementation, we might merge overlapping ranges
    const codeSnippets = sortedNodes
      .map((node) => node.data.codeSnippet)
      .filter((code) => code && code.trim().length > 0);

    if (codeSnippets.length > 0) {
      sources.push({
        file_path: filePath,
        code: codeSnippets.join('\n\n'),
      });
    }
  });

  return sources;
}

export const executeTestCases = (
  body: ExecuteTestCasesRequest,
): Promise<DebuggerPayload> =>
  request<DebuggerPayload>('/execute_test_cases', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export { API_BASE_URL };
