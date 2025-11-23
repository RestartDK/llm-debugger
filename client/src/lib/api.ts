import type {
  ControlFlowResponse,
  DebuggerPayload,
  ExecuteTestCasesRequest,
} from './types';

type Json = Record<string, unknown>;

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
    // Base URL for the backend API server
    // Backend routes: /get_control_flow_diagram, /execute_test_cases, etc.
    // Full URL example: https://coolify.scottbot.party/llm_debugger/get_control_flow_diagram
    return 'https://coolify.scottbot.party/llm_debugger';
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

// Backend route: @app.get("/get_control_flow_diagram") from main.py
// Full URL: https://coolify.scottbot.party/llm_debugger/get_control_flow_diagram
export const fetchControlFlow = (): Promise<ControlFlowResponse> =>
  request<ControlFlowResponse>('/get_control_flow_diagram');

export const executeTestCases = (
  body: ExecuteTestCasesRequest,
): Promise<DebuggerPayload> =>
  request<DebuggerPayload>('/execute_test_cases', {
    method: 'POST',
    body: JSON.stringify(body),
  });

export { API_BASE_URL };

