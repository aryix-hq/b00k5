const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('b00k5_token') || localStorage.getItem('token');
    const tenantId =
      localStorage.getItem('b00k5_active_tenant_id') ||
      localStorage.getItem('b00k5_tenant_id') ||
      localStorage.getItem('tenant_id');

    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    if (tenantId) {
      headers['X-Tenant-ID'] = tenantId;
    }
  }

  return headers;
}

export async function fetchRawApi(endpoint: string, options: RequestInit = {}): Promise<Response> {
  const baseHeaders = getAuthHeaders();
  
  // If sending FormData, omit Content-Type so browser sets boundary multipart/form-data
  if (options.body instanceof FormData) {
    delete baseHeaders['Content-Type'];
  }

  const headers = {
    ...baseHeaders,
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorDetail = `API request failed with status ${response.status}`;
    try {
      const errJson = await response.json();
      errorDetail = errJson.detail || errorDetail;
    } catch (e) {
      // not JSON
    }
    throw new Error(errorDetail);
  }

  return response;
}

export async function fetchApi(endpoint: string, options: RequestInit = {}) {
  const response = await fetchRawApi(endpoint, options);
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return response.json();
  }
  if (contentType.includes('text/')) {
    return response.text();
  }
  return response.blob();
}
