import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, type DocumentAPI, type HubAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';
import DocumentVersionHistory from '../components/DocumentVersionHistory';
import DocumentDiffPreview from '../components/DocumentDiffPreview';
import type { DocumentDiffPreview as DocumentDiffPreviewType } from '../services/api';
import type { RAGDocument } from '../types';
import { cn } from '../lib/utils';
import { motion, AnimatePresence } from 'motion/react';
import RichTextEditor from '../components/RichTextEditor';
import EditContentModal from '../components/EditContentModal';
import Pagination from '../components/Pagination';
import {
  Upload,
  File,
  CheckCircle2,
  Clock,
  AlertCircle,
  Trash2,
  Database,
  ChevronRight,
  Loader2,
  FileText,
  Info,
  ChevronDown,
  Cpu,
  Layers,
  Zap,
  Globe,
  Edit3,
  Link as LinkIcon,
  Plus,
  ArrowLeft,
  Search,
  Filter,
  FileSpreadsheet,
  Presentation,
  FileCode,
  Sparkles,
  MoreVertical,
  BookOpen,
  Eye,
  Download,
  X
} from 'lucide-react';

// TODO: Production → set true (Hub Tổng chỉ nhận từ Hub con qua Sync)
// DEBUG: set false tạm để test nạp tri thức trên Hub Tổng
const IS_HUB_TONG = false;

function mapDocToRAG(doc: DocumentAPI): RAGDocument {
  const formatSize = (bytes: number): string => {
    if (bytes >= 1048576) return (bytes / 1048576).toFixed(1) + ' MB';
    if (bytes >= 1024) return (bytes / 1024).toFixed(0) + ' KB';
    return bytes + ' B';
  };
  return {
    id: doc.id,
    name: doc.name,
    type: doc.file_type as any,
    size: formatSize(doc.file_size),
    hubId: doc.hub_id,
    status: doc.status as any,
    progress: doc.progress,
    chunkCount: doc.chunk_count,
    uploadedAt: doc.uploaded_at,
    uploadedBy: doc.uploaded_by || 'Admin',
    errorMessage: doc.error_message,
  };
}

export default function DocumentIngestion({ mode = 'list' }: { mode?: 'list' | 'new' }) {
  const navigate = useNavigate();
  const [selectedHub, setSelectedHub] = useState('');
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [documents, setDocuments] = useState<RAGDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalDocs, setTotalDocs] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'compose' | 'url'>('upload');
  const [composedTitle, setComposedTitle] = useState('');
  const [composedContent, setComposedContent] = useState('');
  const [importUrl, setImportUrl] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [actionMenuId, setActionMenuId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const [ragConfig, setRagConfig] = useState<{ chunker: string; chunk_size: number; chunk_overlap: number; embedding_model: string; embedding_provider: string } | null>(null);
  const [previewDoc, setPreviewDoc] = useState<RAGDocument | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewTab, setPreviewTab] = useState<'preview' | 'history'>('preview');
  const { user } = useAuth();
  const isAdmin = !!user?.roles?.some(r => r.role === 'admin');
  const reuploadInputRef = useRef<HTMLInputElement>(null);
  const reuploadDocIdRef = useRef<string | null>(null);
  const itemsPerPage = 10;

  // ─── Diff preview state — cho cả flow reupload + edit content ───
  const [diffOpen, setDiffOpen] = useState(false);
  const [diffPreview, setDiffPreview] = useState<DocumentDiffPreviewType | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);
  const [diffConfirming, setDiffConfirming] = useState(false);
  const [diffMode, setDiffMode] = useState<'reupload' | 'edit' | null>(null);
  const [diffDocId, setDiffDocId] = useState<string | null>(null);
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingContent, setPendingContent] = useState<string>('');

  // Modal sửa nội dung markdown — thay cho window.prompt(). Mở từ
  // triggerEditContent() sau khi tải xong nội dung hiện tại.
  const [editModalOpen, setEditModalOpen] = useState(false);
  const [editModalContent, setEditModalContent] = useState('');
  const [editModalDocId, setEditModalDocId] = useState<string | null>(null);
  const [editModalDocName, setEditModalDocName] = useState<string | undefined>(undefined);
  const [editModalLoading, setEditModalLoading] = useState(false);

  const triggerReupload = (docId: string) => {
    reuploadDocIdRef.current = docId;
    reuploadInputRef.current?.click();
  };

  const handleReuploadFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    const docId = reuploadDocIdRef.current;
    e.target.value = '';
    reuploadDocIdRef.current = null;
    if (!file || !docId) return;

    // Mở modal diff với loading, gọi preview API.
    setDiffMode('reupload');
    setDiffDocId(docId);
    setPendingFile(file);
    setPendingContent('');
    setDiffPreview(null);
    setDiffOpen(true);
    setDiffLoading(true);
    try {
      const res = await api.previewReuploadDocument(docId, file);
      if (res.success && res.data) {
        setDiffPreview(res.data);
      } else {
        alert('Không lấy được preview: ' + (res.error?.message || 'Không rõ lý do'));
        setDiffOpen(false);
      }
    } catch (err) {
      alert('Lỗi preview: ' + (err instanceof Error ? err.message : 'Unknown'));
      setDiffOpen(false);
    } finally {
      setDiffLoading(false);
    }
  };

  // Edit content flow — chỉ áp dụng cho .md/.txt/.csv/.html.
  const triggerEditContent = async (docId: string) => {
    const doc = documents.find((d) => d.id === docId);
    setEditModalDocId(docId);
    setEditModalDocName(doc?.name);
    setEditModalContent('');
    setEditModalLoading(true);
    setEditModalOpen(true);
    try {
      const res = await fetch(`/api/documents/${docId}/file`, {
        headers: { Authorization: `Bearer ${localStorage.getItem('access_token')}` },
      });
      if (!res.ok) {
        alert('Không tải được nội dung hiện tại');
        setEditModalOpen(false);
        return;
      }
      const currentContent = await res.text();
      setEditModalContent(currentContent);
    } finally {
      setEditModalLoading(false);
    }
  };

  // Callback từ EditContentModal: null = huỷ, string = nhận nội dung mới và
  // chuyển sang DocumentDiffPreview để user xác nhận trước khi re-embed.
  const handleEditModalClose = async (newContent: string | null) => {
    const docId = editModalDocId;
    setEditModalOpen(false);
    if (newContent === null || docId === null || newContent === editModalContent) {
      setEditModalDocId(null);
      return;
    }

    setDiffMode('edit');
    setDiffDocId(docId);
    setPendingContent(newContent);
    setPendingFile(null);
    setDiffPreview(null);
    setDiffOpen(true);
    setDiffLoading(true);
    try {
      const res = await api.previewEditDocumentContent(docId, newContent);
      if (res.success && res.data) {
        setDiffPreview(res.data);
      } else {
        alert('Không lấy được preview: ' + (res.error?.message || 'Không rõ lý do'));
        setDiffOpen(false);
      }
    } finally {
      setDiffLoading(false);
      setEditModalDocId(null);
    }
  };

  const handleDiffConfirm = async () => {
    if (!diffDocId || !diffMode) return;
    setDiffConfirming(true);
    try {
      if (diffMode === 'reupload' && pendingFile) {
        const res = await api.reuploadDocument(diffDocId, pendingFile);
        if (!res.success) {
          alert('Tải lại file thất bại: ' + (res.error?.message || 'Không rõ lý do'));
          return;
        }
      } else if (diffMode === 'edit') {
        const res = await api.editDocumentContent(diffDocId, pendingContent);
        if (!res.success) {
          alert('Sửa nội dung thất bại: ' + (res.error?.message || 'Không rõ lý do'));
          return;
        }
      }
      setDiffOpen(false);
      setDiffPreview(null);
      setPendingFile(null);
      setPendingContent('');
      await loadDocs();
    } finally {
      setDiffConfirming(false);
    }
  };

  const handleDiffCancel = () => {
    if (diffConfirming) return;
    setDiffOpen(false);
    setDiffPreview(null);
    setPendingFile(null);
    setPendingContent('');
    setDiffMode(null);
    setDiffDocId(null);
  };

  // Phase 5 PROXY-02 fix: dùng absolute path /api/* — Caddy route → central.
  // Endpoint documents/file là per-hub NHƯNG admin page chỉ access từ central context,
  // dùng absolute /api/* để KHÔNG bị double-prefix bug (cũ: API_URL hardcode :8180).

  const handlePreview = async (doc: RAGDocument) => {
    setPreviewDoc(doc);
    setPreviewUrl(null);
    setPreviewTab('preview');
    setPreviewLoading(true);
    try {
      const token = localStorage.getItem('access_token');
      const res = await fetch(`/api/documents/${doc.id}/file`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        setPreviewUrl(url);
      } else {
        setPreviewUrl('error');
      }
    } catch {
      setPreviewUrl('error');
    }
    setPreviewLoading(false);
  };

  const closePreview = () => {
    if (previewUrl && previewUrl !== 'error') URL.revokeObjectURL(previewUrl);
    setPreviewDoc(null);
    setPreviewUrl(null);
  };

  // Fetch hubs + RAG config
  useEffect(() => {
    api.getHubs().then(res => {
      if (res.success && res.data) {
        const active = res.data.filter(h => h.status === 'active');
        setHubs(active);
        if (active.length > 0 && !selectedHub) setSelectedHub(active[0].id);
      }
    });
    fetch('/api/rag-config')
      .then(r => r.json()).then(setRagConfig).catch(() => {});
  }, []);

  // Fetch documents when hub/page changes
  const loadDocs = async () => {
    if (!selectedHub) return;
    setLoading(true);
    const res = await api.getDocuments({ hub_id: selectedHub, page: currentPage, per_page: itemsPerPage });
    if (res.success && res.data) {
      setDocuments(res.data.map(mapDocToRAG));
      setTotalDocs(res.meta?.total || res.data.length);
    }
    setLoading(false);
  };

  useEffect(() => {
    loadDocs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedHub, currentPage]);

  // Poll status for processing documents
  // Poll status for pending/processing documents
  const activeDocs = useMemo(() =>
    documents.filter(d => d.status === 'pending' || d.status === 'processing'),
    [documents]
  );

  useEffect(() => {
    if (activeDocs.length === 0) return;

    const poll = async () => {
      for (const doc of activeDocs) {
        try {
          const res = await api.getDocumentStatus(doc.id);
          if (res.success && res.data) {
            const newStatus = res.data.status as any;
            const newProgress = res.data.progress;
            if (newStatus !== doc.status || newProgress !== doc.progress) {
              setDocuments(prev => prev.map(d =>
                d.id === doc.id ? { ...d, status: newStatus, progress: newProgress } : d
              ));
            }
          }
        } catch { /* ignore */ }
      }
    };

    poll(); // poll immediately
    const interval = setInterval(poll, 1500);
    return () => clearInterval(interval);
  }, [activeDocs.map(d => d.id).join(',')]);

  const filteredDocuments = useMemo(() => {
    return documents.filter(doc => doc.name.toLowerCase().includes(searchQuery.toLowerCase()));
  }, [documents, searchQuery]);

  const totalPages = Math.ceil(totalDocs / itemsPerPage);

  const paginatedDocuments = useMemo(() => {
    // When using server-side pagination, documents are already paginated
    // Client-side filtering only applies to search within current page
    if (searchQuery) {
      return filteredDocuments;
    }
    return documents;
  }, [documents, filteredDocuments, searchQuery]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1); // Reset to first page on search
  };

  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0 || !selectedHub) return;
    setIsUploading(true);

    for (const file of files) {
      try {
        const res = await api.uploadDocument(file, selectedHub);
        if (res.success && res.data) {
          setDocuments(prev => [mapDocToRAG(res.data!), ...prev]);
          setTotalDocs(prev => prev + 1);
        } else {
          console.error('Upload failed:', file.name, res.error?.message);
          alert(`Upload thất bại: ${file.name}\n${res.error?.message || 'Lỗi không xác định'}`);
        }
      } catch (err) {
        console.error('Upload failed:', file.name, err);
        alert(`Upload thất bại: ${file.name}`);
      }
    }

    setIsUploading(false);
    navigate('/documents');
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    await uploadFiles(Array.from(e.dataTransfer.files));
  };

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      await uploadFiles(Array.from(e.target.files));
      e.target.value = ''; // reset input
    }
  };

  const handleIngest = async (type: 'compose' | 'url') => {
    if (!selectedHub) {
      alert('Chưa chọn Hub đích');
      return;
    }
    setIsUploading(true);

    try {
      if (type === 'compose') {
        if (!composedTitle.trim() || !composedContent.trim()) {
          alert('Vui lòng nhập tiêu đề và nội dung');
          setIsUploading(false);
          return;
        }
        const res = await api.composeDocument({
          name: composedTitle.trim(),
          content: composedContent,
          hub_id: selectedHub,
        });
        if (res.success && res.data) {
          setDocuments(prev => [mapDocToRAG(res.data!), ...prev]);
          setTotalDocs(prev => prev + 1);
          setComposedTitle('');
          setComposedContent('');
          navigate('/documents');
        } else {
          alert(`Lỗi: ${res.error?.message || 'Không thể nạp tri thức'}`);
        }
      } else {
        if (!importUrl.trim()) {
          alert('Vui lòng nhập URL');
          setIsUploading(false);
          return;
        }
        const res = await api.composeDocument({
          name: importUrl.split('/').pop() || 'Trang web',
          content: `Nội dung được trích xuất từ URL: ${importUrl}`,
          hub_id: selectedHub,
        });
        if (res.success && res.data) {
          setDocuments(prev => [mapDocToRAG(res.data!), ...prev]);
          setTotalDocs(prev => prev + 1);
          setImportUrl('');
          navigate('/documents');
        } else {
          alert(`Lỗi: ${res.error?.message || 'Không thể nạp tri thức'}`);
        }
      }
    } catch (err) {
      console.error('Ingest failed:', err);
      alert('Lỗi kết nối server');
    }

    setIsUploading(false);
  };

  const getFileIcon = (type: string) => {
    switch (type.toLowerCase()) {
      case 'pdf': return <FileText size={20} className="text-danger" />;
      case 'docx': return <File size={20} className="text-brand-indigo" />;
      case 'xlsx': return <FileSpreadsheet size={20} className="text-success" />;
      case 'pptx': return <Presentation size={20} className="text-orange-500" />;
      case 'txt': return <FileText size={20} className="text-slate-500" />;
      case 'md': return <FileCode size={20} className="text-brand-purple" />;
      default: return <File size={20} className="text-slate-400" />;
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'completed': return <CheckCircle2 className="text-success" size={18} />;
      case 'processing': return <Loader2 className="text-accent animate-spin" size={18} />;
      case 'pending': return <Loader2 className="text-amber-500 animate-spin" size={18} />;
      case 'failed':
      case 'failed_unsupported':
      case 'error': return <AlertCircle className="text-danger" size={18} />;
      default: return <Clock className="text-slate-400" size={18} />;
    }
  };

  // CocoIndex chạy một lượt update_blocking() — KHÔNG có 4 stage progress như
  // backend Go cũ. Trạng thái thực chỉ: pending → completed / failed.
  const getStatusText = (status: string) => {
    switch (status) {
      case 'completed': return 'Đã nạp';
      case 'processing': return 'Đang xử lý...';
      case 'pending': return 'Đang xử lý...';
      case 'failed':
      case 'error': return 'Lỗi';
      case 'failed_unsupported': return 'Không hỗ trợ';
      default: return 'Chờ xử lý';
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedDoc(expandedDoc === id ? null : id);
  };

  return (
    <div className="space-y-8">
      {mode === 'list' ? (
        <div className="space-y-6">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <h1 className="text-h1 font-semibold text-slate-900 dark:text-white">Danh sách tri thức</h1>
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
                {IS_HUB_TONG
                  ? 'Quản lý và duyệt tri thức được đồng bộ từ các Hub con'
                  : 'Quản lý các tri thức đã được nạp vào hệ thống'}
              </p>
            </div>
            {!IS_HUB_TONG && (
              <button
                onClick={() => navigate('/documents/new')}
                className="btn-primary w-full sm:w-auto"
              >
                <Plus size={18} />
                Nạp tri thức mới
              </button>
            )}
          </div>

          <div className="glass-card">
            <div className="p-5 border-b border-slate-100 dark:border-slate-700 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white dark:bg-slate-800 sticky top-0 z-10">
              <div className="relative flex-1 max-w-md">
                <div className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500">
                  <Search size={18} />
                </div>
                <input
                  type="text"
                  placeholder="Tìm kiếm tri thức..."
                  value={searchQuery}
                  onChange={handleSearchChange}
                  className="input-field w-full pl-10"
                />
              </div>
              <div className="flex items-center justify-between sm:justify-end gap-3">
                <button className="btn-secondary">
                  <Filter size={14} />
                  Bộ lọc
                </button>
                <span className="text-xs px-2.5 py-1 bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400 rounded-full">
                  {totalDocs} Tệp tin
                </span>
              </div>
            </div>
            
            <div className="">
              <table className="w-full text-left border-collapse min-w-[800px]">
                <thead>
                  <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                    <th className="px-6 py-4 text-xs font-medium text-slate-500 dark:text-slate-400 w-[40%]">Tri thức</th>
                    <th className="px-6 py-4 text-xs font-medium text-slate-500 dark:text-slate-400 w-[20%]">Hub</th>
                    <th className="px-6 py-4 text-xs font-medium text-slate-500 dark:text-slate-400 w-[20%]">Trạng thái</th>
                    <th className="px-6 py-4 text-xs font-medium text-slate-500 dark:text-slate-400 w-[15%]">Ngày tải</th>
                    <th className="px-6 py-4 text-xs font-medium text-slate-500 dark:text-slate-400 w-[5%]"></th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                  {loading && (
                    <tr>
                      <td colSpan={5} className="px-6 py-16 text-center">
                        <div className="flex flex-col items-center gap-3">
                          <Loader2 className="text-accent animate-spin" size={32} />
                          <span className="text-sm text-slate-500 dark:text-slate-400">Đang tải dữ liệu...</span>
                        </div>
                      </td>
                    </tr>
                  )}
                  {!loading && paginatedDocuments.length === 0 && (
                    <tr>
                      <td colSpan={5} className="px-6 py-16 text-center">
                        <div className="flex flex-col items-center gap-3">
                          <FileText className="text-slate-300 dark:text-slate-600" size={40} />
                          <span className="text-sm text-slate-500 dark:text-slate-400">Chưa có tri thức nào</span>
                        </div>
                      </td>
                    </tr>
                  )}
                  <AnimatePresence>
                    {!loading && paginatedDocuments.map((doc) => (
                      <React.Fragment key={doc.id}>
                        <motion.tr 
                          initial={{ opacity: 0 }}
                          animate={{ opacity: 1 }}
                          exit={{ opacity: 0, x: -20 }}
                          className={cn(
                            "hover:bg-slate-50/50 dark:hover:bg-slate-700 transition-colors group cursor-pointer",
                            expandedDoc === doc.id && "bg-slate-50/80 dark:bg-slate-800/50"
                          )}
                          onClick={() => toggleExpand(doc.id)}
                        >
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-3">
                              <div className="w-10 h-10 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                                {getFileIcon(doc.type)}
                              </div>
                              <div>
                                <div className="text-sm font-bold text-slate-900 dark:text-white group-hover:text-brand-indigo transition-colors">{doc.name}</div>
                                <div className="text-xs text-slate-400 dark:text-slate-500 mt-0.5">{doc.size} • {doc.type}</div>
                              </div>
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="flex items-center gap-2 text-sm text-slate-600 dark:text-slate-300">
                              <Database size={14} className="text-slate-400 dark:text-slate-500" />
                              {hubs.find(h => h.id === doc.hubId)?.name || doc.hubId}
                            </div>
                          </td>
                          <td className="px-6 py-4">
                            <div className="space-y-2">
                              <div className="flex items-center gap-2">
                                {getStatusIcon(doc.status)}
                                <span className={cn(
                                  "text-xs font-medium",
                                  doc.status === 'completed' ? "text-success" :
                                  (doc.status === 'failed' || doc.status === 'failed_unsupported' || doc.status === 'error') ? "text-danger" :
                                  "text-slate-600 dark:text-slate-300"
                                )}>
                                  {getStatusText(doc.status)}
                                </span>
                              </div>
                              {doc.status === 'processing' && (
                                <div className="w-32 h-1 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                                  <motion.div 
                                    initial={{ width: 0 }}
                                    animate={{ width: `${doc.progress}%` }}
                                    className="h-full bg-accent"
                                  />
                                </div>
                              )}
                            </div>
                          </td>
                          <td className="px-6 py-4 text-sm text-slate-500 dark:text-slate-400">
                            {new Date(doc.uploadedAt).toLocaleDateString('vi-VN')}
                          </td>
                          <td className="px-6 py-4 text-right">
                            <div className="flex items-center justify-end">
                              <div className="relative">
                                <button
                                  onClick={(e) => { e.stopPropagation(); setActionMenuId(actionMenuId === doc.id ? null : doc.id); }}
                                  className={cn(
                                    "p-1.5 rounded-lg transition-all text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700",
                                    actionMenuId === doc.id && "text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700"
                                  )}
                                  title="Thao tác"
                                >
                                  <MoreVertical size={16} />
                                </button>
                                <AnimatePresence>
                                  {actionMenuId === doc.id && (
                                    <>
                                      <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setActionMenuId(null); }} />
                                      <motion.div
                                        initial={{ opacity: 0, scale: 0.95, y: -4 }}
                                        animate={{ opacity: 1, scale: 1, y: 0 }}
                                        exit={{ opacity: 0, scale: 0.95, y: -4 }}
                                        className="absolute right-0 mt-1 w-44 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg z-50 overflow-hidden py-1"
                                      >
                                        <button
                                          onClick={(e) => { e.stopPropagation(); setActionMenuId(null); handlePreview(doc); }}
                                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                        >
                                          <Eye size={14} className="text-brand-indigo" />
                                          Xem file gốc
                                        </button>
                                        <button
                                          onClick={(e) => {
                                            e.stopPropagation();
                                            setActionMenuId(null);
                                            handlePreview(doc);
                                            setTimeout(() => setPreviewTab('history'), 0);
                                          }}
                                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                        >
                                          <Clock size={14} className="text-brand-indigo" />
                                          Lịch sử phiên bản
                                        </button>
                                        {isAdmin && !IS_HUB_TONG && (
                                          <button
                                            onClick={(e) => { e.stopPropagation(); setActionMenuId(null); triggerReupload(doc.id); }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                          >
                                            <Upload size={14} className="text-brand-indigo" />
                                            Tải lại file
                                          </button>
                                        )}
                                        {isAdmin && !IS_HUB_TONG && ['md','txt','csv','html'].includes(doc.type.toLowerCase()) && (
                                          <button
                                            onClick={(e) => { e.stopPropagation(); setActionMenuId(null); triggerEditContent(doc.id); }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                          >
                                            <Edit3 size={14} className="text-brand-indigo" />
                                            Sửa nội dung
                                          </button>
                                        )}
                                        <button
                                          onClick={(e) => { e.stopPropagation(); setActionMenuId(null); }}
                                          className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                        >
                                          <Sparkles size={14} className="text-brand-indigo" />
                                          Phân tích bằng AI
                                        </button>
                                        {!IS_HUB_TONG && (
                                          <button
                                            onClick={async (e) => {
                                              e.stopPropagation();
                                              setActionMenuId(null);
                                              const res = await api.deleteDocument(doc.id);
                                              if (res.success) {
                                                setDocuments(prev => prev.filter(d => d.id !== doc.id));
                                                setTotalDocs(prev => prev - 1);
                                              }
                                            }}
                                            className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-danger hover:bg-danger/5 transition-colors"
                                          >
                                            <Trash2 size={14} />
                                            Xóa tri thức
                                          </button>
                                        )}
                                      </motion.div>
                                    </>
                                  )}
                                </AnimatePresence>
                              </div>
                            </div>
                          </td>
                        </motion.tr>
                        
                        <AnimatePresence>
                          {expandedDoc === doc.id && (
                            <motion.tr
                              initial={{ opacity: 0, height: 0 }}
                              animate={{ opacity: 1, height: 'auto' }}
                              exit={{ opacity: 0, height: 0 }}
                              className="bg-slate-50/50 dark:bg-slate-800/50"
                            >
                              <td colSpan={5} className="px-6 py-5 border-t border-slate-100 dark:border-slate-700">
                                <div className="space-y-4">
                                  {/* Trạng thái xử lý — CocoIndex chạy một lượt update_blocking():
                                      pending → completed / failed. KHÔNG có 4 stage như backend Go cũ. */}
                                  <div className={cn(
                                    "flex items-start gap-3 p-3 rounded-lg border",
                                    doc.status === 'completed'
                                      ? "bg-success/5 border-success/20"
                                      : (doc.status === 'failed' || doc.status === 'failed_unsupported' || doc.status === 'error')
                                      ? "bg-danger/5 border-danger/20"
                                      : "bg-accent/5 border-accent/20"
                                  )}>
                                    {doc.status === 'completed' ? (
                                      <CheckCircle2 size={18} className="text-success shrink-0 mt-0.5" />
                                    ) : (doc.status === 'failed' || doc.status === 'failed_unsupported' || doc.status === 'error') ? (
                                      <AlertCircle size={18} className="text-danger shrink-0 mt-0.5" />
                                    ) : (
                                      <Loader2 size={18} className="text-accent animate-spin shrink-0 mt-0.5" />
                                    )}
                                    <div className="text-sm">
                                      {doc.status === 'completed' ? (
                                        <>
                                          <p className="font-medium text-slate-800 dark:text-slate-100">Đã nạp vào kho tri thức</p>
                                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            CocoIndex đã trích xuất, chia chunk và vector hóa — {doc.chunkCount ?? 0} chunks.
                                          </p>
                                        </>
                                      ) : (doc.status === 'failed' || doc.status === 'failed_unsupported' || doc.status === 'error') ? (
                                        <>
                                          <p className="font-medium text-slate-800 dark:text-slate-100">Nạp tri thức thất bại</p>
                                          <p className="text-xs text-danger mt-0.5">{doc.errorMessage || 'Không rõ nguyên nhân'}</p>
                                        </>
                                      ) : (
                                        <>
                                          <p className="font-medium text-slate-800 dark:text-slate-100">Đang xử lý qua CocoIndex</p>
                                          <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                                            Trích xuất · chia chunk · embed chạy nền trong một lượt — trạng thái tự cập nhật khi hoàn tất.
                                          </p>
                                        </>
                                      )}
                                    </div>
                                  </div>

                                  {/* Thông tin kỹ thuật - 1 dòng */}
                                  <div className="flex flex-wrap gap-x-6 gap-y-2 text-xs text-slate-500 dark:text-slate-400">
                                    <div className="flex items-center gap-1.5">
                                      <Layers size={13} className="text-slate-400 dark:text-slate-500" />
                                      <span className="text-slate-700 dark:text-slate-200 font-medium">{ragConfig?.chunker || 'Semantic Chunker'}</span>
                                      <span>· {ragConfig?.chunk_size || 512} tokens · overlap {ragConfig?.chunk_overlap || 50}</span>
                                    </div>
                                    <div className="flex items-center gap-1.5">
                                      <Cpu size={13} className="text-slate-400 dark:text-slate-500" />
                                      <span className="text-slate-700 dark:text-slate-200 font-medium">{ragConfig?.embedding_model || 'gemini-embedding-001'}</span>
                                    </div>
                                  </div>
                                </div>
                              </td>
                            </motion.tr>
                          )}
                        </AnimatePresence>
                      </React.Fragment>
                    ))}
                  </AnimatePresence>
                </tbody>
              </table>
            </div>

            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              onPageChange={setCurrentPage}
              totalItems={totalDocs}
              itemsPerPage={itemsPerPage}
            />
          </div>
        </div>
      ) : IS_HUB_TONG ? (
        // Hub tổng không có chức năng nạp tri thức mới, redirect về danh sách
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <BookOpen size={48} className="text-slate-300 dark:text-slate-600 mb-4" />
          <h2 className="text-h3 font-semibold text-slate-700 dark:text-slate-200 mb-2">Chức năng tạm ẩn</h2>
          <p className="text-sm text-slate-500 dark:text-slate-400 mb-6">Hub tổng chỉ nhận và duyệt tri thức từ các Hub con.</p>
          <button onClick={() => navigate('/documents')} className="btn-secondary">
            <ArrowLeft size={16} />
            Quay lại danh sách
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/documents')}
              className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-full transition-colors text-slate-500 dark:text-slate-400"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="text-h1 font-semibold text-slate-900 dark:text-white">Nạp tri thức mới</h1>
              <p className="text-slate-500 dark:text-slate-400">Chọn phương thức nạp tri thức vào kho dữ liệu Hub Tổng</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-8 space-y-6">
              <div className="glass-card overflow-hidden">
                <div className="flex p-1 bg-slate-100 dark:bg-slate-700 m-4 rounded-xl overflow-x-auto no-scrollbar">
                  <div className="flex min-w-full">
                    {[
                      { id: 'upload', icon: Upload, label: 'Tải lên tệp tin' },
                      { id: 'compose', icon: Edit3, label: 'Soạn thảo văn bản' },
                      { id: 'url', icon: Globe, label: 'Trích xuất từ URL' }
                    ].map((tab) => (
                      <button
                        key={tab.id}
                        onClick={() => setActiveTab(tab.id as any)}
                        className={cn(
                          "flex-1 flex items-center justify-center gap-2 py-3 px-4 text-xs sm:text-sm font-bold rounded-lg transition-all whitespace-nowrap",
                          activeTab === tab.id
                            ? "bg-white dark:bg-slate-800 text-slate-900 dark:text-white shadow-sm"
                            : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
                        )}
                      >
                        <tab.icon size={16} />
                        {tab.label}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="p-6 pt-2">
                  <AnimatePresence mode="wait">
                    {activeTab === 'upload' && (
                      <motion.div 
                        key="upload"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        onDragOver={handleDragOver}
                        onDragLeave={handleDragLeave}
                        onDrop={handleDrop}
                        className={cn(
                          "border-2 border-dashed rounded-2xl p-6 sm:p-12 flex flex-col items-center justify-center text-center transition-all duration-200 min-h-[300px] sm:min-h-[400px]",
                          isDragging ? "border-accent bg-accent/5" : "border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-800 hover:border-slate-300 dark:hover:border-slate-600",
                          isUploading && "opacity-50 pointer-events-none"
                        )}
                      >
                        <div className="w-20 h-20 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center mb-6">
                          {isUploading ? (
                            <Loader2 className="text-accent animate-spin" size={40} />
                          ) : (
                            <Upload className="text-slate-400 dark:text-slate-500" size={40} />
                          )}
                        </div>
                        <h3 className="text-h3 font-semibold text-slate-800 dark:text-slate-100 mb-2">
                          {isUploading ? "Đang xử lý tri thức..." : "Kéo thả tệp tin vào đây"}
                        </h3>
                        <p className="text-slate-500 dark:text-slate-400 mb-8 max-w-sm">
                          Hỗ trợ PDF, DOCX, TXT, MD. Tối đa 20MB. Hệ thống sẽ tự động OCR và trích xuất nội dung.
                        </p>
                        <input
                          ref={fileInputRef}
                          type="file"
                          multiple
                          accept=".pdf,.docx,.txt,.md,.xlsx,.pptx,.jpg,.png,.csv,.html"
                          onChange={handleFileSelect}
                          className="hidden"
                        />
                        <button
                          onClick={() => fileInputRef.current?.click()}
                          disabled={isUploading || !selectedHub}
                          className="btn-secondary"
                        >
                          Chọn tệp từ máy tính
                        </button>
                      </motion.div>
                    )}

                    {activeTab === 'compose' && (
                      <motion.div 
                        key="compose"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="space-y-6"
                      >
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Tiêu đề tri thức</label>
                          <input 
                            type="text" 
                            value={composedTitle}
                            onChange={(e) => setComposedTitle(e.target.value)}
                            placeholder="Ví dụ: Quy trình vận hành nội bộ..." 
                            className="input-field w-full font-medium"
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Nội dung chi tiết</label>
                          <RichTextEditor 
                            content={composedContent}
                            onChange={setComposedContent}
                            placeholder="Bắt đầu soạn thảo nội dung của bạn..." 
                          />
                        </div>
                        <div className="flex justify-end gap-3 pt-4">
                          <button 
                            onClick={() => navigate('/documents')}
                            className="btn-secondary"
                          >
                            Hủy bỏ
                          </button>
                          <button 
                            onClick={() => handleIngest('compose')}
                            disabled={!composedTitle || !composedContent || isUploading}
                            className="btn-primary"
                          >
                            {isUploading ? <Loader2 size={18} className="animate-spin" /> : <Zap size={18} />}
                            Nạp vào hệ thống
                          </button>
                        </div>
                      </motion.div>
                    )}

                    {activeTab === 'url' && (
                      <motion.div 
                        key="url"
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                        className="space-y-8 py-12 flex flex-col items-center max-w-2xl mx-auto"
                      >
                        <div className="w-20 h-20 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                          <Globe className="text-slate-400 dark:text-slate-500" size={40} />
                        </div>
                        <div className="text-center space-y-2">
                          <h3 className="text-h3 font-semibold text-slate-800 dark:text-slate-100">Trích xuất từ địa chỉ Web</h3>
                          <p className="text-slate-500 dark:text-slate-400">
                            Nhập URL của bài viết hoặc tri thức trực tuyến, hệ thống sẽ tự động làm sạch và trích xuất văn bản.
                          </p>
                        </div>
                        <div className="w-full relative">
                          <div className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500">
                            <LinkIcon size={20} />
                          </div>
                          <input 
                            type="url" 
                            value={importUrl}
                            onChange={(e) => setImportUrl(e.target.value)}
                            placeholder="https://example.com/knowledge-base/article-1" 
                            className="input-field w-full pl-12"
                          />
                        </div>
                        <button 
                          onClick={() => handleIngest('url')}
                          disabled={!importUrl || isUploading}
                          className="btn-primary w-full"
                        >
                          {isUploading ? <Loader2 size={20} className="animate-spin" /> : <Globe size={20} />}
                          Bắt đầu trích xuất nội dung
                        </button>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </div>
              </div>
            </div>

            <div className="lg:col-span-4 space-y-6">
              <div className="glass-card p-6 space-y-6">
                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-500 dark:text-slate-400">Kho tri thức đích</label>
                  <div className="input-field w-full flex items-center gap-2 bg-slate-50 dark:bg-slate-700/50">
                    <Database size={14} className="text-brand-indigo" />
                    <span className="font-medium text-slate-700 dark:text-slate-200">
                      {hubs.find(h => h.id === selectedHub)?.name || 'Hub Tổng'}
                    </span>
                  </div>
                  <p className="text-[11px] text-slate-400 dark:text-slate-500">Tri thức sẽ được vector hóa và lưu trữ vào kho dữ liệu này.</p>
                </div>

                <div className="pt-4 border-t border-slate-100 dark:border-slate-700 space-y-4">
                  <div className="flex items-center gap-2 text-xs font-medium text-slate-500 dark:text-slate-400">
                    <Info size={14} />
                    Lưu ý quan trọng
                  </div>
                  <div className="space-y-4">
                    {[
                      { title: "Cấu trúc rõ ràng", desc: "Tri thức có tiêu đề và phân đoạn sẽ giúp AI hiểu tốt hơn." },
                      { title: "Chất lượng file", desc: "Tránh các file scan mờ hoặc không có lớp văn bản (OCR)." },
                      { title: "Tự động Chunking", desc: "Hệ thống sẽ tự động chia nhỏ tri thức để tối ưu tìm kiếm." },
                      { title: "Bảo mật dữ liệu", desc: "Dữ liệu được mã hóa và chỉ có thể truy cập từ Hub đã chọn." }
                    ].map((item, i) => (
                      <div key={i} className="flex items-start gap-3">
                        <div className="w-5 h-5 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5">
                          {i + 1}
                        </div>
                        <div>
                          <p className="text-xs font-semibold text-slate-800 dark:text-slate-100">{item.title}</p>
                          <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">{item.desc}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Hidden file input cho thao tác "Tải lại file" — admin only */}
      <input
        ref={reuploadInputRef}
        type="file"
        className="hidden"
        onChange={handleReuploadFile}
      />

      {/* Modal sửa nội dung markdown — split editor + preview, thay window.prompt() */}
      <EditContentModal
        open={editModalOpen}
        loading={editModalLoading}
        docName={editModalDocName}
        initialContent={editModalContent}
        onClose={handleEditModalClose}
      />

      {/* Modal diff preview — bắt buộc xem khác biệt trước khi confirm vector hóa */}
      <DocumentDiffPreview
        open={diffOpen}
        preview={diffPreview}
        loading={diffLoading}
        confirming={diffConfirming}
        onConfirm={handleDiffConfirm}
        onCancel={handleDiffCancel}
        title={diffMode === 'reupload' ? 'Tải lại file' : 'Sửa nội dung'}
      />

      {/* ─── File Preview Modal ─── */}
      <AnimatePresence>
        {previewDoc && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
            onClick={closePreview}
          >
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 16 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 16 }}
              className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] flex flex-col overflow-hidden"
              onClick={e => e.stopPropagation()}
            >
              {/* Header */}
              <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700 shrink-0">
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center shrink-0">
                    {getFileIcon(previewDoc.type)}
                  </div>
                  <div className="min-w-0">
                    <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{previewDoc.name}</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">{previewDoc.size} · {previewDoc.type.toUpperCase()}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2 shrink-0 ml-4">
                  {previewUrl && previewUrl !== 'error' && (
                    <a
                      href={previewUrl}
                      download={previewDoc.name}
                      className="btn-secondary text-xs px-3 py-1.5"
                    >
                      <Download size={14} />
                      Tải xuống
                    </a>
                  )}
                  <button
                    onClick={closePreview}
                    className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors"
                  >
                    <X size={18} />
                  </button>
                </div>
              </div>

              {/* Tabs */}
              <div className="flex items-center gap-1 px-5 pt-3 border-b border-slate-100 dark:border-slate-700 shrink-0">
                <button
                  onClick={() => setPreviewTab('preview')}
                  className={cn(
                    'px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors',
                    previewTab === 'preview'
                      ? 'border-accent text-accent'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  )}
                >
                  Xem trước
                </button>
                <button
                  onClick={() => setPreviewTab('history')}
                  className={cn(
                    'px-3 py-2 text-xs font-medium border-b-2 -mb-px transition-colors flex items-center gap-1.5',
                    previewTab === 'history'
                      ? 'border-accent text-accent'
                      : 'border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300'
                  )}
                >
                  <Clock size={12} /> Lịch sử phiên bản
                </button>
              </div>

              {/* Body */}
              <div className="flex-1 overflow-auto">
                {previewTab === 'history' && (
                  <div className="p-5">
                    <DocumentVersionHistory
                      documentId={previewDoc.id}
                      canRestore={isAdmin}
                      onRestored={() => loadDocs()}
                    />
                  </div>
                )}

                {previewTab === 'preview' && previewLoading && (
                  <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
                    <Loader2 size={32} className="animate-spin text-accent" />
                    <p className="text-sm text-slate-500 dark:text-slate-400">Đang tải file...</p>
                  </div>
                )}

                {previewTab === 'preview' && !previewLoading && previewUrl === 'error' && (
                  <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
                    <AlertCircle size={40} className="text-danger/60" />
                    <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Không thể tải file</p>
                    <p className="text-xs text-slate-400 dark:text-slate-500">Máy chủ chưa hỗ trợ xem file trực tiếp hoặc file không tồn tại</p>
                  </div>
                )}

                {previewTab === 'preview' && !previewLoading && previewUrl && previewUrl !== 'error' && (() => {
                  const t = previewDoc.type.toLowerCase();
                  if (t === 'pdf') {
                    return (
                      <iframe
                        src={previewUrl}
                        title={previewDoc.name}
                        className="w-full h-full min-h-[60vh]"
                        style={{ border: 'none' }}
                      />
                    );
                  }
                  if (t === 'jpg' || t === 'jpeg' || t === 'png' || t === 'gif' || t === 'webp') {
                    return (
                      <div className="flex items-center justify-center h-full p-6 overflow-auto">
                        <img src={previewUrl} alt={previewDoc.name} className="max-w-full max-h-[70vh] rounded-xl object-contain shadow" />
                      </div>
                    );
                  }
                  if (t === 'txt' || t === 'md') {
                    return (
                      <iframe
                        src={previewUrl}
                        title={previewDoc.name}
                        className="w-full h-full min-h-[60vh]"
                        style={{ border: 'none' }}
                      />
                    );
                  }
                  // DOCX / XLSX / PPTX / CSV / HTML — offer download
                  return (
                    <div className="flex flex-col items-center justify-center h-full py-20 gap-4">
                      <div className="w-16 h-16 rounded-2xl bg-slate-100 dark:bg-slate-700 flex items-center justify-center">
                        {getFileIcon(t)}
                      </div>
                      <div className="text-center">
                        <p className="text-sm font-medium text-slate-700 dark:text-slate-200 mb-1">
                          Không thể xem trực tiếp file <span className="uppercase">{t}</span>
                        </p>
                        <p className="text-xs text-slate-400 dark:text-slate-500 mb-5">Tải xuống để mở bằng ứng dụng phù hợp</p>
                        <a
                          href={previewUrl}
                          download={previewDoc.name}
                          className="btn-primary inline-flex"
                        >
                          <Download size={16} />
                          Tải xuống file
                        </a>
                      </div>
                    </div>
                  );
                })()}
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
