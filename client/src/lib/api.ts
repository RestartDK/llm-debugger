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

  const response = await fetch(buildUrl(path), {
    ...options,
    headers,
  });

  const isJsonResponse =
    response.headers.get('content-type')?.includes('application/json');

  const payload = isJsonResponse ? await response.json() : undefined;

  if (!response.ok) {
    throw new HttpError(
      payload?.message?.toString() ||
        `Request to ${path} failed with status ${response.status}`,
      response.status,
      payload,
    );
  }

  return payload as TResponse;
}

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

