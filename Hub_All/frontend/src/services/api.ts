// Auto-detect backend URL: same hostname as frontend, port 8180
// (8080 is in Windows Hyper-V excluded port range 8038-8137 — use 8180 instead)
const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8180`;

interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string };
  meta?: { page: number; per_page: number; total: number; total_pages: number };
}

class APIClient {
  private baseURL: string;

  constructor(baseURL: string) {
    this.baseURL = baseURL;
  }

  private getToken(): string | null {
    return localStorage.getItem('access_token');
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<APIResponse<T>> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${this.baseURL}${path}`, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
      // Try refresh
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.getToken()}`;
        const retry = await fetch(`${this.baseURL}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
        return retry.json();
      }
      localStorage.removeItem('access_token');
      localStorage.removeItem('refresh_token');
      window.location.href = '/login';
      throw new Error('Session expired');
    }

    return res.json();
  }

  private async tryRefresh(): Promise<boolean> {
    const refreshToken = localStorage.getItem('refresh_token');
    if (!refreshToken) return false;
    try {
      const res = await fetch(`${this.baseURL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!res.ok) return false;
      const data = await res.json();
      if (data.success && data.data) {
        localStorage.setItem('access_token', data.data.access_token);
        localStorage.setItem('refresh_token', data.data.refresh_token);
        return true;
      }
      return false;
    } catch {
      return false;
    }
  }

  // ─── Auth ───
  async login(email: string, password: string, hubId?: string) {
    return this.request<LoginResponse>('POST', '/api/auth/login', { email, password, hub_id: hubId });
  }

  async logout() {
    return this.request<{ message: string }>('POST', '/api/auth/logout');
  }

  async me() {
    return this.request<UserWithRoles>('GET', '/api/auth/me');
  }

  // ─── Hubs ───
  async getHubs() {
    return this.request<HubAPI[]>('GET', '/api/hubs');
  }

  async getHub(id: string) {
    return this.request<HubAPI>('GET', `/api/hubs/${id}`);
  }

  async createHub(data: CreateHubRequest) {
    return this.request<HubAPI>('POST', '/api/hubs', data);
  }

  async updateHub(id: string, data: UpdateHubRequest) {
    return this.request<HubAPI>('PUT', `/api/hubs/${id}`, data);
  }

  async updateHubStatus(id: string, status: string) {
    return this.request<{ message: string }>('PATCH', `/api/hubs/${id}/status`, { status });
  }

  async testHubConnection(id: string) {
    return this.request<{ message: string }>('POST', `/api/hubs/${id}/test-connection`);
  }

  // ─── Documents ───
  async getDocuments(params: { hub_id?: string; status?: string; file_type?: string; page?: number; per_page?: number } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<DocumentAPI[]>('GET', `/api/documents${qs ? '?' + qs : ''}`);
  }

  async getDocument(id: string) {
    return this.request<DocumentAPI>('GET', `/api/documents/${id}`);
  }

  async getDocumentStatus(id: string) {
    return this.request<{ status: string; progress: number }>('GET', `/api/documents/${id}/status`);
  }

  async uploadDocument(file: File, hubId: string) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('hub_id', hubId);

    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(`${this.baseURL}/api/documents/upload`, {
      method: 'POST',
      headers,
      body: formData,
    });
    return res.json() as Promise<APIResponse<DocumentAPI>>;
  }

  async composeDocument(data: { name: string; content: string; hub_id: string }) {
    return this.request<DocumentAPI>('POST', '/api/documents/compose', data);
  }

  async deleteDocument(id: string) {
    return this.request<{ message: string }>('DELETE', `/api/documents/${id}`);
  }

  getDocumentFileUrl(id: string): string {
    return `${this.baseURL}/api/documents/${id}/file`;
  }

  // ─── Document version history (3 gốc + 2 gần nhất) ───
  async listDocumentVersions(id: string) {
    return this.request<{ versions: DocumentVersionAPI[] }>('GET', `/api/documents/${id}/versions`);
  }

  async getDocumentVersion(docId: string, versionId: string) {
    return this.request<{ version: DocumentVersionAPI; chunks: DocumentVersionChunkAPI[] }>(
      'GET', `/api/documents/${docId}/versions/${versionId}`,
    );
  }

  getDocumentVersionFileUrl(docId: string, versionId: string): string {
    return `${this.baseURL}/api/documents/${docId}/versions/${versionId}/file`;
  }

  async restoreDocumentVersion(docId: string, versionId: string) {
    return this.request<DocumentAPI>('POST', `/api/documents/${docId}/versions/${versionId}/restore`);
  }

  async previewReuploadDocument(docId: string, file: File) {
    const formData = new FormData();
    formData.append('file', file);
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${this.baseURL}/api/documents/${docId}/reupload/preview`, {
      method: 'POST', headers, body: formData,
    });
    return res.json() as Promise<APIResponse<DocumentDiffPreview>>;
  }

  async previewEditDocumentContent(docId: string, content: string) {
    return this.request<DocumentDiffPreview>('PUT', `/api/documents/${docId}/content/preview`, { content });
  }

  async reuploadDocument(docId: string, file: File, note?: string) {
    const formData = new FormData();
    formData.append('file', file);
    if (note) formData.append('note', note);
    const token = this.getToken();
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const res = await fetch(`${this.baseURL}/api/documents/${docId}/reupload`, {
      method: 'POST', headers, body: formData,
    });
    return res.json() as Promise<APIResponse<DocumentAPI>>;
  }

  async editDocumentContent(docId: string, content: string, note?: string) {
    return this.request<DocumentAPI>('PUT', `/api/documents/${docId}/content`, { content, note });
  }

  // ─── Search ───
  async search(data: SearchRequestAPI) {
    return this.request<SearchResponseAPI>('POST', '/api/search', data);
  }

  async crossHubSearch(data: SearchRequestAPI) {
    return this.request<SearchResponseAPI>('POST', '/api/search/cross-hub', data);
  }

  async searchAnswer(data: { query: string; hub_ids?: string[]; top_k?: number }) {
    return this.request<SearchAnswerAPI>('POST', '/api/search/answer', data);
  }

  async findSimilar(data: { content: string; hub_id?: string; threshold?: number }) {
    return this.request<SimilarResponseAPI>('POST', '/api/search/similar', data);
  }

  // ─── Sync ───
  async getSyncBatches(params: { hub_id?: string; status?: string; page?: number; per_page?: number } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<SyncBatchAPI[]>('GET', `/api/sync/batches${qs ? '?' + qs : ''}`);
  }

  async getSyncBatch(id: string) {
    return this.request<SyncBatchAPI>('GET', `/api/sync/batches/${id}`);
  }

  async submitSyncBatch(data: { hub_id: string; pages: SubmitSyncPageAPI[] }) {
    return this.request<SyncBatchAPI>('POST', '/api/sync/batches', data);
  }

  async approveSyncPage(batchId: string, pageId: string) {
    return this.request<{ message: string }>('POST', `/api/sync/batches/${batchId}/pages/${pageId}/approve`);
  }

  async rejectSyncPage(batchId: string, pageId: string, reason: string) {
    return this.request<{ message: string }>('POST', `/api/sync/batches/${batchId}/pages/${pageId}/reject`, { reason });
  }

  async getSyncStats() {
    return this.request<{ pending_batches: number; pending_pages: number }>('GET', '/api/sync/stats');
  }

  // ─── Users ───
  async getUsers(params: { hub_id?: string; role?: string; status?: string; search?: string; page?: number; per_page?: number } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<UserWithRolesAPI[]>('GET', `/api/users${qs ? '?' + qs : ''}`);
  }

  async getUser(id: string) {
    return this.request<UserWithRolesAPI>('GET', `/api/users/${id}`);
  }

  async createUser(data: { email: string; name: string; password: string; phone?: string; department?: string; hub_id: string; role: string }) {
    return this.request<UserAPI>('POST', '/api/users', data);
  }

  async updateUser(id: string, data: { name?: string; phone?: string; department?: string }) {
    return this.request<UserAPI>('PUT', `/api/users/${id}`, data);
  }

  async changeUserRole(id: string, hubId: string, role: string) {
    return this.request<{ message: string }>('PATCH', `/api/users/${id}/role`, { hub_id: hubId, role });
  }

  async changeUserStatus(id: string, status: string) {
    return this.request<{ message: string }>('PATCH', `/api/users/${id}/status`, { status });
  }

  // ─── Profile ───
  async getProfile() {
    return this.request<UserWithRolesAPI>('GET', '/api/profile');
  }

  async updateProfile(data: { name?: string; phone?: string; department?: string }) {
    return this.request<UserAPI>('PUT', '/api/profile', data);
  }

  async changePassword(oldPassword: string, newPassword: string) {
    return this.request<{ message: string }>('POST', '/api/profile/password', { old_password: oldPassword, new_password: newPassword });
  }

  // ─── Audit Logs ───
  async getAuditLogs(params: { date_from?: string; date_to?: string; actor_type?: string; action?: string; hub_id?: string; page?: number; per_page?: number } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<AuditLogAPI[]>('GET', `/api/audit-logs${qs ? '?' + qs : ''}`);
  }

  // ─── API Keys ───
  async getAPIKeys(params: { page?: number; per_page?: number } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined) query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<APIKeyAPI[]>('GET', `/api/api-keys${qs ? '?' + qs : ''}`);
  }

  async getAPIKey(id: string) {
    return this.request<APIKeyAPI>('GET', `/api/api-keys/${id}`);
  }

  async createAPIKey(data: { name: string; permissions: string[]; allowed_hub_ids?: string[]; rate_limit?: number }) {
    return this.request<APIKeyWithPlaintextAPI>('POST', '/api/api-keys', data);
  }

  async updateAPIKey(id: string, data: { name?: string; permissions?: string[]; allowed_hub_ids?: string[]; rate_limit?: number }) {
    return this.request<APIKeyAPI>('PUT', `/api/api-keys/${id}`, data);
  }

  async revokeAPIKey(id: string) {
    return this.request<{ message: string }>('POST', `/api/api-keys/${id}/revoke`);
  }

  // ─── AI Chat (backend proxy) ───
  async aiChat(messages: { role: string; content: string }[], systemInstruction?: string) {
    return this.request<{ response: string }>('POST', '/api/ai/chat', {
      messages,
      system_instruction: systemInstruction,
    });
  }

  // ─── Token / API Usage ───
  async getTokenUsage(params: {
    date_from?: string; date_to?: string; provider?: string; model?: string;
    operation?: string; hub_id?: string; status?: string; page?: number; per_page?: number;
  } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<TokenUsageAPI[]>('GET', `/api/usage${qs ? '?' + qs : ''}`);
  }

  async getTokenUsageStats(params: {
    date_from?: string; date_to?: string; provider?: string; model?: string;
    operation?: string; hub_id?: string;
  } = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== '') query.set(k, String(v)); });
    const qs = query.toString();
    return this.request<TokenUsageStatsAPI>('GET', `/api/usage/stats${qs ? '?' + qs : ''}`);
  }

  async getTokenUsageRealtime() {
    return this.request<TokenUsageRealtimeAPI>('GET', '/api/usage/realtime');
  }
}

// ─── API Types ───
export interface LoginResponse {
  access_token: string;
  refresh_token: string;
  expires_at: number;
  user: UserWithRoles;
}

export interface UserWithRoles {
  user: UserAPI;
  roles: RoleAPI[];
}

export interface UserAPI {
  id: string;
  email: string;
  name: string;
  phone?: string;
  department?: string;
  avatar_url?: string;
  status: string;
  failed_login_count: number;
  created_at: string;
  updated_at: string;
}

export interface RoleAPI {
  user_id: string;
  hub_id: string;
  role: string;
}

export interface HubAPI {
  id: string;
  name: string;
  code: string;
  subdomain: string;
  description?: string;
  db_host?: string;
  db_port: number;
  db_name?: string;
  db_user?: string;
  chroma_collection: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface CreateHubRequest {
  name: string;
  code: string;
  subdomain: string;
  description?: string;
  chroma_collection: string;
  db_host?: string;
  db_port?: number;
  db_name?: string;
  db_user?: string;
  db_password?: string;
}

export interface UpdateHubRequest {
  name?: string;
  description?: string;
  db_host?: string;
  db_port?: number;
  db_name?: string;
  db_user?: string;
  db_password?: string;
}

export interface DocumentAPI {
  id: string;
  name: string;
  file_type: string;
  file_size: number;
  file_path: string;
  hub_id: string;
  status: string;
  progress: number;
  error_message?: string;
  chunk_count: number;
  uploaded_by: string;
  uploaded_at: string;
  processed_at?: string;
}

export interface DocumentVersionAPI {
  id: string;
  document_id: string;
  version_number: number;
  is_original: boolean;
  name: string;
  file_type: string;
  file_size: number;
  file_path: string;
  file_hash?: string;
  extractor_used?: string;
  chunk_count: number;
  change_type: 'reupload' | 'reextract' | 'content_edit' | 'restore';
  change_note?: string;
  created_by?: string;
  created_at: string;
}

export interface DocumentDiffMeta {
  name: string;
  file_type: string;
  file_size: number;
  file_hash: string;
}

export interface DocumentDiffPreview {
  is_text: boolean;
  old_text?: string;
  new_text?: string;
  old_meta?: DocumentDiffMeta;
  new_meta?: DocumentDiffMeta;
  note?: string;
}

export interface DocumentVersionChunkAPI {
  id: string;
  version_id: string;
  chunk_index: number;
  content: string;
  token_count: number;
  metadata: Record<string, unknown>;
}

export interface SearchRequestAPI {
  query: string;
  hub_ids?: string[];
  top_k?: number;
  min_score?: number;
  filters?: { categories?: string[]; tags?: string[]; date_from?: string; date_to?: string };
}

export interface SearchResultAPI {
  id: string;
  hub_id: string;
  hub_name: string;
  title: string;
  snippet: string;
  content?: string;
  category?: string;
  tags?: string[];
  score: number;
  raw_similarity: number;
  updated_at?: string;
  source: string;
}

export interface SearchResponseAPI {
  results: SearchResultAPI[];
  total_hubs_searched: number;
  query_time_ms: number;
  cache_hit: boolean;
}

export interface SimilarResponseAPI {
  matches: { page_id: string; page_title: string; similarity_score: number; hub_name: string }[];
}

export interface SyncBatchAPI {
  id: string;
  hub_id: string;
  hub_name: string;
  page_count: number;
  files_summary: Record<string, number>;
  total_size: number;
  submitted_by: string;
  submitted_by_name: string;
  status: string;
  approved_count: number;
  rejected_count: number;
  submitted_at: string;
  completed_at?: string;
  pages?: SyncPageAPI[];
}

export interface SyncPageAPI {
  id: string;
  batch_id: string;
  title: string;
  file_name: string;
  file_type: string;
  file_size: number;
  content: string;
  category?: string;
  tags?: string[];
  author?: string;
  status: string;
  rejection_reason?: string;
  similarity_score?: number;
  similar_page_id?: string;
  similar_page_title?: string;
  reviewed_by?: string;
  reviewed_at?: string;
  created_at: string;
}

export interface SubmitSyncPageAPI {
  title: string;
  file_name: string;
  file_type: string;
  file_size: number;
  content: string;
  category?: string;
  tags?: string[];
  author?: string;
}

export interface UserWithRolesAPI {
  user: UserAPI;
  roles: RoleAPI[];
}

export interface AuditLogAPI {
  id: string;
  timestamp: string;
  user_id?: string;
  user_name?: string;
  is_ai: boolean;
  action: string;
  target?: string;
  hub_id?: string;
  hub_name?: string;
  ip_address?: string;
  user_agent?: string;
  request_id?: string;
  duration_ms?: number;
  payload?: unknown;
}

export interface APIKeyAPI {
  id: string;
  name: string;
  key_prefix: string;
  permissions: string[];
  allowed_hub_ids?: string[];
  allowed_rag_configs?: string[];
  rate_limit: number;
  expires_at?: string;
  status: string;
  requests_today: number;
  requests_7d: number;
  bandwidth_used: number;
  last_used_at?: string;
  created_by: string;
  created_at: string;
}

export interface APIKeyWithPlaintextAPI extends APIKeyAPI {
  plain_key: string;
}

export interface CitationRefAPI {
  id: string;            // chunk id the LLM cited
  marker: string;        // literal "[src:<id>]" string in answer
  number: number;        // 1-based ordinal for display
  document_id: string;
  document_name: string;
  hub_name: string;
  chunk_index: number;
  snippet: string;
  score: number;
}

export interface SearchAnswerAPI {
  answer: string;
  sources: { doc_name: string; hub_name: string; snippet: string; score: number }[];
  citations?: CitationRefAPI[];
  search_results: SearchResultAPI[];
  query_time_ms: number;
  model: string;
}

export interface TokenUsageAPI {
  id: string;
  timestamp: string;
  provider: string;
  model: string;
  operation: string;
  source_module?: string;
  user_id?: string;
  user_name?: string;
  hub_id?: string;
  request_count: number;
  prompt_tokens: number;
  output_tokens: number;
  total_tokens: number;
  latency_ms: number;
  status: string;
  error_message?: string;
}

export interface TokenUsageGroupAPI {
  key: string;
  calls: number;
  total_tokens: number;
}

export interface TokenUsageDailyPointAPI {
  date: string;
  calls: number;
  total_tokens: number;
}

export interface TokenUsageStatsAPI {
  total_calls: number;
  total_tokens: number;
  total_prompt_tokens: number;
  total_output_tokens: number;
  error_calls: number;
  avg_latency_ms: number;
  by_provider: TokenUsageGroupAPI[];
  by_model: TokenUsageGroupAPI[];
  by_operation: TokenUsageGroupAPI[];
  daily: TokenUsageDailyPointAPI[];
}

export interface TokenUsageRealtimePoint {
  minute: string;
  calls: number;
  total_tokens: number;
  prompt_tokens: number;
  output_tokens: number;
  avg_latency_ms: number;
  errors: number;
  by_provider: Record<string, number>;
  by_operation: Record<string, number>;
}

export interface TokenUsageRealtimeAPI {
  window_minutes: number;
  points: TokenUsageRealtimePoint[];
  totals: TokenUsageRealtimePoint;
}

export const api = new APIClient(API_URL);
