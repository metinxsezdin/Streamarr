export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function joinUrl(baseUrl: string, path: string): string {
  if (/^https?:/i.test(path)) {
    return path;
  }

  const normalizedBase = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${normalizedBase}${normalizedPath}`;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  if (!text) {
    return undefined as T;
  }

  try {
    return JSON.parse(text) as T;
  } catch (error) {
    throw new ApiError(response.status, "Failed to parse response body", {
      cause: error,
      body: text,
    });
  }
}

async function request<T>(
  baseUrl: string,
  token: string | undefined,
  path: string,
  init: RequestInit & { body?: unknown } = {},
): Promise<T> {
  const headers: Record<string, string> = {
    Accept: "application/json",
    ...(init.headers as Record<string, string> | undefined),
  };

  let body: BodyInit | undefined = init.body as BodyInit | undefined;
  if (init.body !== undefined && typeof init.body !== "string") {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(init.body);
  }

  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const response = await fetch(joinUrl(baseUrl, path), {
    ...init,
    headers,
    body,
  });

  if (!response.ok) {
    let detail: unknown;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(
      response.status,
      `Request failed with status ${response.status}`,
      detail,
    );
  }

  return parseResponse<T>(response);
}

export interface ApiClient {
  baseUrl: string;
  token?: string;
  get<T>(path: string, init?: RequestInit): Promise<T>;
  post<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
  put<T>(path: string, body?: unknown, init?: RequestInit): Promise<T>;
}

export function createApiClient(baseUrl: string, token?: string): ApiClient {
  return {
    baseUrl,
    token,
    get: (path, init) => request(baseUrl, token, path, { ...init, method: "GET" }),
    post: (path, body, init) =>
      request(baseUrl, token, path, { ...init, method: "POST", body }),
    put: (path, body, init) =>
      request(baseUrl, token, path, { ...init, method: "PUT", body }),
  };
}
