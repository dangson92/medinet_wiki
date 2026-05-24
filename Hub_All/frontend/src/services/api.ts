// Phase 5 D-V3-Phase5-B1 LOCKED — 1-build prefix detect (replaces M2 absolute origin hardcode)
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Implementation Decisions B1"
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-RESEARCH.md Pattern 2 + Pitfall 4
//
// T-5-02 (Tampering hub allowlist client-side): Frontend allowlist chỉ làm UX routing.
// Backend Caddy `path_regexp ^/(yte|duoc|hcns)/api/(.*)$` (Plan 05-01) là real authority —
// tamper window.__HUB_CONFIG__.allowlist từ DevTools KHÔNG bypass backend strip; only thay
// đổi client-side route handling. KHÔNG dùng FE allowlist làm trust boundary.

// Runtime hub config — Caddy/backend inject via <script>window.__HUB_CONFIG__=...</script>
// HOẶC fallback hardcode 3 hub initial Phase 5 (Phase 6 SETTINGS-04 sync DB-driven hub_registry).
interface HubConfigRuntime {
  allowlist: readonly string[];
  current?: string; // optional — chỉ set nếu backend render dynamic
}

declare global {
  interface Window {
    __HUB_CONFIG__?: HubConfigRuntime;
  }
}

const HUB_CONFIG: HubConfigRuntime = (typeof window !== 'undefined' && window.__HUB_CONFIG__) ?? {
  // Fallback hardcode initial 3 hub gốc Phase 5 — synced with Plan 05-01 .env.example HUBS_ALLOWLIST_REGEX
  allowlist: ['yte', 'duoc', 'hcns'] as const,
};

const KNOWN_HUBS: readonly string[] = HUB_CONFIG.allowlist;

const firstSegment: string | undefined =
  typeof window !== 'undefined'
    ? window.location.pathname.split('/').filter(Boolean)[0]
    : undefined;

// PREFIX null nếu segment KHÔNG match KNOWN_HUBS (T-5-02: backend Caddy regex authoritative,
// FE allowlist chỉ UX routing — unknown prefix fall through to central context)
export const PREFIX: string | null =
  firstSegment && KNOWN_HUBS.includes(firstSegment) ? firstSegment : null;

// API_BASE KHÔNG kèm '/api' — path trong this.request('METHOD', '/api/...') tự chứa prefix.
// Hub yte: baseURL='/yte' + path='/api/auth/login' → '/yte/api/auth/login' (Caddy strip /yte → upstream /api/auth/login).
// Central: baseURL=''  + path='/api/auth/login' → '/api/auth/login' (Caddy /api/* → python-api-central).
// Fix double-prefix regression Plan 05-02 commit 8eb0676 (cũ: '/api' + '/api/...' → '/api/api/...' → 404).
export const API_BASE: string = PREFIX ? `/${PREFIX}` : '';
export const APP_BASE: string = PREFIX ? `/${PREFIX}` : '';
export const CURRENT_HUB: string = PREFIX ?? 'central';

// API_URL relative — Caddy same-origin gateway (KHÔNG cần absolute hostname:port nữa)
const API_URL = API_BASE;

interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: { code: string; message: string; details?: Record<string, unknown> };
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

  /**
   * Phase 5 D-V3-Phase4-D3 + RESEARCH §7 Option A — gọi central absolute path.
   * KHÔNG dùng this.baseURL prefix. Dùng cho endpoint central-only như /api/search/cross-hub
   * mà hub con strip (FACTOR-02 extend Phase 4) → 404 envelope D6.
   *
   * Caddy /api/* handle block (Plan 05-01) → reverse_proxy python-api-central:8080 (no strip).
   */
  private async requestAbsolute<T>(method: string, absolutePath: string, body?: unknown): Promise<APIResponse<T>> {
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    const token = this.getToken();
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const res = await fetch(absolutePath, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
    });

    if (res.status === 401) {
      const refreshed = await this.tryRefresh();
      if (refreshed) {
        headers['Authorization'] = `Bearer ${this.getToken()}`;
        const retry = await fetch(absolutePath, { method, headers, body: body ? JSON.stringify(body) : undefined });
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
      // D-V3-Phase5-C4 LOCKED — preserve POST body through 307 redirect from hub con → central
      // Plan 03-04 SSO-02: hub con POST /api/auth/refresh → 307 RedirectResponse Location: ${CENTRAL_URL}/api/auth/refresh
      // RFC 7231 §6.4.7: 307 MUST preserve method + body. Browser fetch default redirect mode is 'follow'
      // but we set EXPLICIT for clarity + audit trail (B-02 fix per plan-checker iteration 1).
      const res = await fetch(`${this.baseURL}/api/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
        redirect: 'follow',
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

  /**
   * Cross-hub search — central-only endpoint (D-V3-Phase4-D3 LOCKED Phase 4 + RESEARCH §7 Option A).
   *
   * CRITICAL: Always uses ABSOLUTE path '/api/search/cross-hub' (KHÔNG ${this.baseURL} prefix).
   * Lý do: hub con strip endpoint (FACTOR-02 extend) → 404 envelope D6. Frontend phải bypass
   * API_BASE prefix để đảm bảo reach central qua Caddy /api/* handle (Plan 05-01).
   */
  async crossHubSearch(data: SearchRequestAPI) {
    return this.requestAbsolute<SearchResponseAPI>('POST', '/api/search/cross-hub', data);
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

  async deleteUser(id: string) {
    return this.request<{ message: string }>('DELETE', `/api/users/${id}`);
  }

  async resetUserPassword(id: string) {
    return this.request<{ password: string; message: string }>(
      'POST', `/api/users/${id}/reset-password`,
    );
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

  // ─── MCP OAuth Client (Phase 8.3 per-user pre-registered) ───
  // User mở Profile → tab MCP Connector → GET lazy-create cặp riêng để dán
  // vào dialog "Add custom connector" → Advanced của Claude web. Rotate đổi
  // client_secret nếu nghi rò rỉ.
  async getMyMCPOAuthClient() {
    return this.request<MCPOAuthClientAPI>('GET', '/api/mcp/my-oauth-client');
  }

  async rotateMyMCPOAuthClient() {
    return this.request<MCPOAuthClientAPI>('POST', '/api/mcp/my-oauth-client/rotate');
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

// Plan 03-01 v3.1 Phase 3 FE-04 — UserRole literal union mirror BE Pydantic Literal
// Source: .planning/phases/02-backend-rbac-enforcement/02-CONTEXT.md D-V3.1-Phase2-A LOCKED
//         api/app/schemas/users.py:UserRole = Literal["admin","hub_admin","editor","viewer"]
//         .planning/phases/01-rbac-schema-migration/01-01-PLAN.md migration 0006 CHECK constraint
//         .planning/phases/03-frontend-form-refactor/03-CONTEXT.md D-V3.1-Phase3-D LOCKED
//
// CRITICAL: Drift giữa FE alias + BE Literal + Phase 1 CHECK constraint → 422 reject runtime.
// Centralize export tại đây (api.ts) — consumer import qua `import type { UserRole } from '../services/api'`.
export type UserRole = 'admin' | 'hub_admin' | 'editor' | 'viewer';

export interface UserAPI {
  id: string;
  email: string;
  name: string;
  phone?: string;
  department?: string;
  avatar_url?: string;
  status: string;
  role: UserRole;  // Plan 03-01 v3.1 Phase 3 FE-04 — BE Phase 2 ship qua /api/auth/me (D-V3.1-Phase3-B LOCKED)
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

// Per-user pre-registered MCP OAuth client (Phase 8.3 add-on).
// Shape khớp MCPOAuthClientResponse ở api/app/schemas/mcp_oauth.py.
// `client_secret` trả plaintext — user copy dán vào dialog Claude Advanced.
export interface MCPOAuthClientAPI {
  client_id: string;
  client_secret: string;
  redirect_uris: string[];
  created_at: string;
  rotated_at: string | null;
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
