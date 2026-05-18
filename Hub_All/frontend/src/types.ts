export interface Hub {
  id: string;
  name: string;
  code: string;
  subdomain: string;
  pages: number;
  users: number;
  lastUpdate: string;
  status: 'active' | 'inactive';
  pendingSync: number;
  createdAt: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  role: 'admin' | 'viewer';
  hubId: string;
  createdAt: string;
  lastLogin: string;
  status: 'active' | 'disabled';
}

export type FileType = 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' | 'md' | 'jpg' | 'png' | 'csv' | 'html';

export interface SyncBatch {
  id: string;
  hubId: string;
  hubName: string;
  pageCount: number;
  submittedAt: string;
  submittedBy: string;
  status: 'pending' | 'processed';
  processedCount?: { approved: number; rejected: number };
  filesSummary: Partial<Record<FileType, number>>;
  totalSize: string;
}

export interface SyncPage {
  id: string;
  batchId: string;
  title: string;
  fileName: string;
  fileType: FileType;
  fileSize: string;
  category: string;
  tags: string[];
  content: string;
  author: string;
  createdAt: string;
  status: 'pending' | 'approved' | 'rejected';
  rejectionReason?: string;
  similarityScore?: number;
  similarPageTitle?: string;
}

export interface AuditLogEntry {
  id: string;
  timestamp: string;
  user: string;
  isAI: boolean;
  action: 'CREATE' | 'UPDATE' | 'DELETE' | 'SYNC' | 'APPROVE_SYNC' | 'REJECT_SYNC' | 'LOGIN' | 'MCP_READ' | 'MCP_WRITE';
  target: string;
  hub: string;
  ip: string;
  userAgent?: string;
  requestId?: string;
  durationMs?: number;
  payload?: unknown;
}

export interface APIKey {
  id: string;
  name: string;
  permissions: string[];
  allowedHubs: string[];
  allowedRAGConfigs?: string[];
  createdAt: string;
  lastUsed: string;
  requests7d: number;
  requestsToday: number;
  bandwidthUsed: string;
  rateLimit: number;
  status: 'active' | 'revoked';
}

export interface RAGDocument {
  id: string;
  name: string;
  type: 'pdf' | 'docx' | 'txt' | 'md' | 'xlsx' | 'pptx';
  size: string;
  hubId: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'failed_unsupported' | 'error';
  progress: number;
  chunkCount?: number;
  uploadedAt: string;
  uploadedBy: string;
  errorMessage?: string;
  content?: string;
}
