import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, CURRENT_HUB, type DocumentAPI, type HubAPI } from '../services/api';
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
import { DocxPreview } from '../components/DocxPreview';
import { XlsxPreview } from '../components/XlsxPreview';
import { CsvPreview } from '../components/CsvPreview';
import FileTypeIcon from '../components/FileTypeIcon';
import {
  Upload,
  UploadCloud,
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
  const [previewBlob, setPreviewBlob] = useState<Blob | null>(null);
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
    setPreviewBlob(null);
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
        setPreviewBlob(blob);
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
    setPreviewBlob(null);
  };

  // Fetch hubs + RAG config
  useEffect(() => {
    api.getHubs().then(res => {
      if (res.success && res.data) {
        const active = res.data.filter(h => h.status === 'active');
        setHubs(active);
        if (active.length > 0 && !selectedHub) {
          // Mặc định chọn hub trùng URL prefix (CURRENT_HUB) thay vì active[0] —
          // KHÔNG có match thì fallback hub đầu tiên.
          const currentHub = active.find(h => h.code === CURRENT_HUB) ?? active[0];
          setSelectedHub(currentHub.id);
        }
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
      case 'pdf': return <FileText size={20} className="text-error" />;
      case 'docx': return <File size={20} className="text-primary" />;
      case 'xlsx': return <FileSpreadsheet size={20} className="text-emerald-600" />;
      case 'pptx': return <Presentation size={20} className="text-orange-500" />;
      case 'txt': return <FileText size={20} className="text-on-surface-variant" />;
      case 'md': return <FileCode size={20} className="text-tertiary" />;
      default: return <File size={20} className="text-outline" />;
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
          {/* Mẫu giao-dien-mau danh_sach_tri_thuc — header h1 + subtitle + count badge + Bộ lọc */}
          <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4">
            <div>
              <h1 className="font-display text-headline-xl text-on-surface dark:text-white">Danh sách tri thức</h1>
              <p className="text-body-sm text-on-surface-variant mt-1">
                {IS_HUB_TONG
                  ? 'Quản lý và duyệt tri thức được đồng bộ từ các Hub con'
                  : 'Quản lý các tri thức đã được nạp vào hệ thống'}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <div className="bg-surface-container-low px-3 py-2 rounded-lg text-[11px] font-bold text-outline border border-outline-variant uppercase tracking-wider">
                {totalDocs} Tệp tin
              </div>
              <button className="flex items-center gap-2 px-4 py-2 border border-outline-variant rounded-lg text-body-sm font-semibold text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:border-slate-700 dark:hover:bg-slate-800">
                <Filter size={18} />
                Bộ lọc
              </button>
            </div>
          </div>

          {/* Search input — mẫu rounded-xl border-outline-variant max-w-xl */}
          <div className="relative max-w-xl">
            <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-outline pointer-events-none" />
            <input
              type="text"
              placeholder="Tìm kiếm tri thức..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="w-full bg-white border border-outline-variant rounded-xl py-2.5 pl-11 pr-4 text-body-md shadow-sm focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none dark:bg-slate-800 dark:border-slate-700 dark:text-white"
            />
          </div>

          {/* Table header — mẫu grid 5 col uppercase outline */}
          <div className="hidden lg:grid grid-cols-[1.5fr_1fr_140px_120px_56px] gap-6 px-6 py-3 text-[11px] font-bold text-outline uppercase tracking-wider">
            <div>Tri thức</div>
            <div>Hub tham chiếu</div>
            <div>Trạng thái</div>
            <div>Ngày tải</div>
            <div></div>
          </div>

          {/* Document list — card-per-row */}
          <div className="space-y-3">
            {loading && (
              <div className="m3-card p-10 flex flex-col items-center gap-3">
                <Loader2 className="text-primary animate-spin" size={32} />
                <span className="text-body-sm text-on-surface-variant">Đang tải dữ liệu...</span>
              </div>
            )}
            {!loading && paginatedDocuments.length === 0 && (
              <div className="m3-card p-10 flex flex-col items-center gap-3">
                <FileText className="text-outline-variant" size={40} />
                <span className="text-body-sm text-on-surface-variant">Chưa có tri thức nào</span>
              </div>
            )}
            <AnimatePresence>
              {!loading && paginatedDocuments.map((doc) => {
                const isExpanded = expandedDoc === doc.id;
                const isOk = doc.status === 'completed';
                const isErr = doc.status === 'failed' || doc.status === 'failed_unsupported' || doc.status === 'error';
                const isProcessing = !isOk && !isErr;
                return (
                  <motion.div
                    key={doc.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0, x: -20 }}
                    className={cn(
                      "group bg-white rounded-xl transition-all cursor-pointer dark:bg-slate-800",
                      isExpanded
                        ? "border border-primary/40 shadow-md"
                        : "border border-outline-variant shadow-sm hover:shadow-md hover:border-primary/40 dark:border-slate-700"
                    )}
                    onClick={() => toggleExpand(doc.id)}
                  >
                    {/* Main row */}
                    <div className="p-4 lg:grid lg:grid-cols-[1.5fr_1fr_140px_120px_56px] gap-6 items-center flex flex-col sm:flex-row sm:items-center sm:gap-4">
                      <div className="flex items-center gap-4 min-w-0 flex-1">
                        <div className={cn(
                          "w-10 h-10 rounded-lg flex items-center justify-center shrink-0 bg-white",
                          isExpanded ? "border border-primary/20" : "border border-outline-variant/30"
                        )}>
                          {/* Mẫu giao-dien-mau — logo Office thực (W/X/P/PDF) */}
                          <FileTypeIcon fileName={doc.name} size={28} />
                        </div>
                        <div className="min-w-0">
                          <h3 className={cn(
                            "text-body-sm font-bold truncate transition-colors",
                            isExpanded ? "text-primary" : "text-on-surface group-hover:text-primary dark:text-white"
                          )}>
                            {doc.name}
                          </h3>
                          <p className="text-[11px] text-on-surface-variant">{doc.size} • {doc.type}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="px-2 py-0.5 bg-primary text-on-primary text-[10px] rounded font-bold truncate max-w-[140px]">
                          {hubs.find((h) => h.id === doc.hubId)?.name || doc.hubId}
                        </span>
                      </div>
                      <div className={cn(
                        "flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-tight",
                        isOk && "text-emerald-600",
                        isErr && "text-error",
                        isProcessing && "text-on-surface-variant"
                      )}>
                        {isOk ? <CheckCircle2 size={16} /> : isErr ? <AlertCircle size={16} /> : <Loader2 size={16} className="animate-spin" />}
                        {getStatusText(doc.status)}
                      </div>
                      <div className="text-[11px] text-on-surface-variant font-medium">
                        {new Date(doc.uploadedAt).toLocaleDateString('vi-VN')}
                      </div>
                      <div className="flex justify-end items-center gap-1 relative">
                        <button
                          onClick={(e) => { e.stopPropagation(); handlePreview(doc); }}
                          className={cn(
                            "p-1.5 hover:bg-surface-container rounded-lg transition-colors",
                            isExpanded ? "text-primary" : "text-outline"
                          )}
                          title="Xem tệp gốc"
                        >
                          <Eye size={20} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setActionMenuId(actionMenuId === doc.id ? null : doc.id); }}
                          className={cn(
                            "p-1.5 hover:bg-surface-container rounded-lg transition-colors",
                            isExpanded || actionMenuId === doc.id ? "text-primary" : "text-outline"
                          )}
                          title="Thao tác"
                        >
                          <MoreVertical size={20} />
                        </button>
                        <AnimatePresence>
                          {actionMenuId === doc.id && (
                            <>
                              <div className="fixed inset-0 z-40" onClick={(e) => { e.stopPropagation(); setActionMenuId(null); }} />
                              <motion.div
                                initial={{ opacity: 0, scale: 0.95, y: -4 }}
                                animate={{ opacity: 1, scale: 1, y: 0 }}
                                exit={{ opacity: 0, scale: 0.95, y: -4 }}
                                className="absolute right-0 top-full mt-1 w-56 bg-white border border-outline-variant rounded-lg shadow-xl z-50 overflow-hidden py-1 dark:bg-slate-800 dark:border-slate-700"
                              >
                                <button
                                  onClick={(e) => { e.stopPropagation(); setActionMenuId(null); handlePreview(doc); }}
                                  className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:hover:bg-slate-700"
                                >
                                  <Eye size={18} />
                                  Xem file gốc
                                </button>
                                <button
                                  onClick={(e) => {
                                    e.stopPropagation();
                                    setActionMenuId(null);
                                    handlePreview(doc);
                                    setTimeout(() => setPreviewTab('history'), 0);
                                  }}
                                  className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:hover:bg-slate-700"
                                >
                                  <Clock size={18} />
                                  Lịch sử phiên bản
                                </button>
                                {isAdmin && !IS_HUB_TONG && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setActionMenuId(null); triggerReupload(doc.id); }}
                                    className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:hover:bg-slate-700"
                                  >
                                    <Upload size={18} />
                                    Tải lại file
                                  </button>
                                )}
                                {isAdmin && !IS_HUB_TONG && ['md','txt','csv','html'].includes(doc.type.toLowerCase()) && (
                                  <button
                                    onClick={(e) => { e.stopPropagation(); setActionMenuId(null); triggerEditContent(doc.id); }}
                                    className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:hover:bg-slate-700"
                                  >
                                    <Edit3 size={18} />
                                    Sửa nội dung
                                  </button>
                                )}
                                <button
                                  onClick={(e) => { e.stopPropagation(); setActionMenuId(null); }}
                                  className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-on-surface hover:bg-surface-container-low transition-colors dark:text-white dark:hover:bg-slate-700"
                                >
                                  <Sparkles size={18} />
                                  Phân tích bằng AI
                                </button>
                                {!IS_HUB_TONG && (
                                  <>
                                    <div className="h-px bg-outline-variant/30 my-1" />
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
                                      className="w-full flex items-center gap-3 px-4 py-2 text-body-sm text-error hover:bg-error/5 transition-colors"
                                    >
                                      <Trash2 size={18} />
                                      Xóa tri thức
                                    </button>
                                  </>
                                )}
                              </motion.div>
                            </>
                          )}
                        </AnimatePresence>
                      </div>
                    </div>

                    {/* Expanded extraction info — mẫu bg-primary/5 p-4 pl-16 */}
                    <AnimatePresence>
                      {isExpanded && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="bg-primary/5 border-t border-outline-variant/10 overflow-hidden rounded-b-xl"
                        >
                          <div className="p-4 lg:pl-16">
                            <div className="flex items-start gap-3 mb-3">
                              {isOk ? <CheckCircle2 size={18} className="text-emerald-600 mt-0.5 shrink-0" />
                                : isErr ? <AlertCircle size={18} className="text-error mt-0.5 shrink-0" />
                                : <Loader2 size={18} className="text-primary animate-spin mt-0.5 shrink-0" />}
                              <div className="flex-1">
                                <p className="text-body-sm font-bold text-on-surface dark:text-white">
                                  {isOk ? 'Đã trích xuất thành công'
                                    : isErr ? 'Nạp tri thức thất bại'
                                    : 'Đang xử lý qua CocoIndex'}
                                </p>
                                <p className="text-[11px] text-on-surface-variant">
                                  {isOk ? `Hệ thống đã hoàn tất xử lý ${doc.chunkCount ?? 0} chunks dữ liệu từ tệp tin này.`
                                    : isErr ? (doc.errorMessage || 'Không rõ nguyên nhân')
                                    : 'Trích xuất · chia chunk · embed chạy nền trong một lượt — trạng thái tự cập nhật khi hoàn tất.'}
                                </p>
                              </div>
                            </div>
                            {isOk && (
                              <div className="flex flex-wrap gap-2 mt-2">
                                <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant font-medium bg-white px-2 py-1 rounded border border-outline-variant/40 dark:bg-slate-900 dark:border-slate-700">
                                  <Layers size={14} className="text-primary" />
                                  {ragConfig?.chunker || 'Semantic Chunker'} • {ragConfig?.chunk_size || 512} tokens
                                </div>
                                <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant font-medium bg-white px-2 py-1 rounded border border-outline-variant/40 dark:bg-slate-900 dark:border-slate-700">
                                  <Cpu size={14} className="text-primary" />
                                  {ragConfig?.embedding_model || 'text-embedding-3-small'}
                                </div>
                              </div>
                            )}
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </motion.div>
                );
              })}
            </AnimatePresence>
          </div>

          {/* Pagination */}
          <Pagination
            currentPage={currentPage}
            totalPages={totalPages}
            onPageChange={setCurrentPage}
            totalItems={totalDocs}
            itemsPerPage={itemsPerPage}
          />
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
          {/* Mẫu giao-dien-mau nap_tri_thuc — header: back round + h1 headline-xl + subtitle */}
          <div className="flex items-center gap-4">
            <button
              onClick={() => navigate('/documents')}
              className="w-10 h-10 flex items-center justify-center rounded-full border border-outline-variant hover:bg-white hover:shadow-sm transition-all text-on-surface dark:border-slate-700 dark:hover:bg-slate-800 dark:text-white"
              title="Quay lại danh sách"
            >
              <ArrowLeft size={20} />
            </button>
            <div>
              <h1 className="font-display text-headline-xl text-on-surface dark:text-white">Nạp tri thức mới</h1>
              <p className="text-body-md text-on-surface-variant mt-1">Chọn phương thức nạp tri thức vào kho dữ liệu Hub Tổng</p>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
            {/* LEFT col-span-8: upload card + 3 feature chips */}
            <div className="lg:col-span-8 space-y-6">
              {/* Mẫu — bento card với tabs underline + content padding lg */}
              <div className="m3-card overflow-hidden">
                <div className="flex border-b border-outline-variant bg-surface-container-lowest dark:bg-slate-900 overflow-x-auto no-scrollbar">
                  {[
                    { id: 'upload', icon: Upload, label: 'Tải lên tệp tin' },
                    { id: 'compose', icon: Edit3, label: 'Soạn thảo văn bản' },
                    { id: 'url', icon: Globe, label: 'Trích xuất từ URL' }
                  ].map((tab) => (
                    <button
                      key={tab.id}
                      onClick={() => setActiveTab(tab.id as any)}
                      className={cn(
                        "flex-1 py-4 px-6 flex items-center justify-center gap-2 text-body-sm font-semibold transition-all whitespace-nowrap border-b-2",
                        activeTab === tab.id
                          ? "border-primary text-primary font-bold"
                          : "border-transparent text-on-surface-variant hover:bg-surface-container-low dark:hover:bg-slate-700/50"
                      )}
                    >
                      <tab.icon size={20} />
                      {tab.label}
                    </button>
                  ))}
                </div>

                <div className="p-8">
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
                          "border-2 border-dashed rounded-xl bg-surface-container-low/30 p-8 sm:p-12 flex flex-col items-center justify-center text-center transition-all duration-200 group min-h-[320px]",
                          isDragging ? "border-primary bg-primary/5" : "border-outline-variant hover:border-primary/50",
                          isUploading && "opacity-50 pointer-events-none"
                        )}
                      >
                        <div className="w-20 h-20 bg-primary/10 rounded-full flex items-center justify-center mb-6 group-hover:scale-110 transition-transform">
                          {isUploading ? (
                            <Loader2 className="text-primary animate-spin" size={40} />
                          ) : (
                            <UploadCloud className="text-primary" size={40} />
                          )}
                        </div>
                        <h3 className="font-display text-headline-md text-on-surface dark:text-white mb-2">
                          {isUploading ? "Đang xử lý tri thức..." : "Kéo thả tệp tin vào đây"}
                        </h3>
                        <p className="text-body-md text-on-surface-variant mb-8 max-w-md">
                          Hỗ trợ PDF, DOCX, TXT, MD. Tối đa 20MB.
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
                          className="px-8 py-3 bg-white border border-outline-variant rounded-full text-body-sm font-bold text-on-surface hover:shadow-md hover:border-primary active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed dark:bg-slate-800 dark:border-slate-700 dark:text-white"
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
                          <label className="text-label-md font-bold text-on-surface-variant uppercase tracking-wider">Tiêu đề tri thức</label>
                          <input
                            type="text"
                            value={composedTitle}
                            onChange={(e) => setComposedTitle(e.target.value)}
                            placeholder="Ví dụ: Quy trình vận hành nội bộ..."
                            className="w-full bg-white border border-outline-variant rounded-xl px-4 py-2.5 text-body-md text-on-surface font-medium shadow-sm focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none dark:bg-slate-800 dark:border-slate-700 dark:text-white"
                          />
                        </div>
                        <div className="space-y-2">
                          <label className="text-label-md font-bold text-on-surface-variant uppercase tracking-wider">Nội dung chi tiết</label>
                          <RichTextEditor
                            content={composedContent}
                            onChange={setComposedContent}
                            placeholder="Bắt đầu soạn thảo nội dung của bạn..."
                          />
                        </div>
                        <div className="flex justify-end gap-3 pt-4 border-t border-outline-variant">
                          <button
                            onClick={() => navigate('/documents')}
                            className="px-5 py-2.5 bg-white border border-outline-variant rounded-full text-body-sm font-semibold text-on-surface hover:bg-surface-container-low transition-colors dark:bg-slate-800 dark:border-slate-700 dark:text-white"
                          >
                            Hủy bỏ
                          </button>
                          <button
                            onClick={() => handleIngest('compose')}
                            disabled={!composedTitle || !composedContent || isUploading}
                            className="inline-flex items-center gap-2 px-5 py-2.5 bg-primary text-on-primary rounded-full text-body-sm font-bold hover:bg-primary-container transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
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
                        className="space-y-8 py-8 flex flex-col items-center max-w-2xl mx-auto"
                      >
                        <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                          <Globe className="text-primary" size={40} />
                        </div>
                        <div className="text-center space-y-2">
                          <h3 className="font-display text-headline-md text-on-surface dark:text-white">Trích xuất từ địa chỉ Web</h3>
                          <p className="text-body-md text-on-surface-variant">
                            Nhập URL của bài viết hoặc tri thức trực tuyến, hệ thống sẽ tự động làm sạch và trích xuất văn bản.
                          </p>
                        </div>
                        <div className="w-full relative">
                          <LinkIcon size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none" />
                          <input
                            type="url"
                            value={importUrl}
                            onChange={(e) => setImportUrl(e.target.value)}
                            placeholder="https://example.com/knowledge-base/article-1"
                            className="w-full bg-white border border-outline-variant rounded-xl pl-12 pr-4 py-3 text-body-md text-on-surface shadow-sm focus:ring-4 focus:ring-primary/10 focus:border-primary transition-all outline-none dark:bg-slate-800 dark:border-slate-700 dark:text-white"
                          />
                        </div>
                        <button
                          onClick={() => handleIngest('url')}
                          disabled={!importUrl || isUploading}
                          className="inline-flex items-center justify-center gap-2 w-full px-5 py-3 bg-primary text-on-primary rounded-full text-body-sm font-bold hover:bg-primary-container transition-all shadow-sm disabled:opacity-50 disabled:cursor-not-allowed"
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

            {/* RIGHT col-span-4: target hub + notes */}
            <div className="lg:col-span-4 space-y-6">
              {/* Mẫu — Kho tri thức đích */}
              <div className="m3-card p-6">
                <h4 className="text-label-md font-bold text-on-surface-variant uppercase tracking-wider mb-4">Kho tri thức đích</h4>
                <div className="p-4 bg-primary/5 border border-primary/20 rounded-xl flex items-center gap-3">
                  <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center shrink-0">
                    <Database size={18} className="text-on-primary" />
                  </div>
                  <div className="min-w-0">
                    <p className="text-body-md font-bold text-on-surface dark:text-white truncate">
                      {hubs.find((h) => h.id === selectedHub)?.name || 'Chưa chọn Hub'}
                    </p>
                    <p className="text-[11px] text-on-surface-variant leading-tight">
                      Tri thức sẽ được vector hóa và lưu trữ vào kho dữ liệu này.
                    </p>
                  </div>
                </div>
              </div>

              {/* Mẫu — Lưu ý quan trọng với 4 numbered items */}
              <div className="m3-card p-6">
                <div className="flex items-center gap-2 mb-6">
                  <Info size={20} className="text-amber-500" />
                  <h4 className="text-label-md font-bold text-on-surface-variant uppercase tracking-wider">Lưu ý quan trọng</h4>
                </div>
                <div className="space-y-5">
                  {[
                    { title: 'Cấu trúc rõ ràng', desc: 'Tri thức có tiêu đề và phân đoạn sẽ giúp AI hiểu tốt hơn.' },
                    { title: 'Chất lượng file', desc: 'Tránh các file scan mờ hoặc không có lớp văn bản (OCR).' },
                    { title: 'Tự động Chunking', desc: 'Hệ thống sẽ tự động chia nhỏ tri thức để tối ưu tìm kiếm.' },
                    { title: 'Bảo mật dữ liệu', desc: 'Dữ liệu được mã hóa và chỉ có thể truy cập từ Hub đã chọn.' },
                  ].map((item, i) => (
                    <div key={i} className="flex gap-4">
                      <span className="flex-shrink-0 w-6 h-6 rounded-full bg-surface-container-highest text-[12px] font-bold flex items-center justify-center text-on-surface dark:bg-slate-700 dark:text-white">
                        {i + 1}
                      </span>
                      <div>
                        <h5 className="text-body-md font-bold text-on-surface dark:text-white">{item.title}</h5>
                        <p className="text-body-sm text-on-surface-variant">{item.desc}</p>
                      </div>
                    </div>
                  ))}
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
                  if (t === 'html' || t === 'htm') {
                    return (
                      <iframe
                        src={previewUrl}
                        title={previewDoc.name}
                        sandbox=""
                        className="w-full h-full min-h-[60vh] bg-white"
                        style={{ border: 'none' }}
                      />
                    );
                  }
                  if (t === 'docx' && previewBlob) {
                    return <DocxPreview blob={previewBlob} />;
                  }
                  if (t === 'xlsx' && previewBlob) {
                    return <XlsxPreview blob={previewBlob} />;
                  }
                  if (t === 'csv' && previewBlob) {
                    return <CsvPreview blob={previewBlob} />;
                  }
                  // PPTX (chưa có lib lightweight) + format khác — offer download
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
