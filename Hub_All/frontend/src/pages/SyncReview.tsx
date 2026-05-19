import React, { useState, useEffect } from 'react';
import { api, type SyncBatchAPI, type SyncPageAPI } from '../services/api';
import type { SyncPage } from '../types';
import { cn } from '../lib/utils';
import { Check, X, ChevronLeft, User, Calendar, Tag, AlertCircle, ArrowRight, Menu, FileText, File, FileSpreadsheet, Presentation, FileCode, Image, Globe, Database as TableIcon, HardDrive, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useParams, useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function mapPage(p: SyncPageAPI): SyncPage {
  return {
    id: p.id,
    batchId: p.batch_id,
    title: p.title,
    fileName: p.file_name,
    fileType: p.file_type as SyncPage['fileType'],
    fileSize: formatBytes(p.file_size),
    category: p.category || '',
    tags: p.tags || [],
    content: p.content,
    author: p.author || '',
    createdAt: p.created_at ? new Date(p.created_at).toLocaleDateString('vi-VN') : '',
    status: p.status as SyncPage['status'],
    rejectionReason: p.rejection_reason,
    similarityScore: p.similarity_score,
    similarPageTitle: p.similar_page_title,
  };
}

const SyncReview = () => {
  const { batchId } = useParams();
  const navigate = useNavigate();

  const [pages, setPages] = useState<SyncPage[]>([]);
  const [loading, setLoading] = useState(true);
  const [isProcessed, setIsProcessed] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [rejectionReason, setRejectionReason] = useState('');
  const [showRejectInput, setShowRejectInput] = useState(false);
  const [isSidebarOpen, setIsSidebarOpen] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  const FILE_TYPE_ICON: Record<string, { icon: React.ElementType; color: string }> = {
    pdf: { icon: FileText, color: 'text-red-500 bg-red-50' },
    docx: { icon: File, color: 'text-blue-600 bg-blue-50' },
    xlsx: { icon: FileSpreadsheet, color: 'text-emerald-600 bg-emerald-50' },
    pptx: { icon: Presentation, color: 'text-orange-500 bg-orange-50' },
    txt: { icon: FileText, color: 'text-slate-500 bg-slate-100' },
    md: { icon: FileCode, color: 'text-violet-600 bg-violet-50' },
    jpg: { icon: Image, color: 'text-pink-500 bg-pink-50' },
    png: { icon: Image, color: 'text-teal-500 bg-teal-50' },
    csv: { icon: TableIcon, color: 'text-green-600 bg-green-50' },
    html: { icon: Globe, color: 'text-amber-600 bg-amber-50' },
  };

  useEffect(() => {
    if (!batchId) return;
    let cancelled = false;
    const fetchBatch = async () => {
      setLoading(true);
      try {
        const res = await api.getSyncBatch(batchId);
        if (cancelled) return;
        if (res.success && res.data) {
          setIsProcessed(res.data.status !== 'pending');
          const mappedPages = (res.data.pages || []).map(mapPage);
          setPages(mappedPages);
        }
      } catch (err) {
        console.error('Failed to fetch batch:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchBatch();
    return () => { cancelled = true; };
  }, [batchId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full gap-3">
        <Loader2 size={24} className="animate-spin text-brand-indigo" />
        <span className="text-sm text-slate-500 dark:text-slate-400">Đang tải dữ liệu...</span>
      </div>
    );
  }

  const activePage = pages[activeIndex];
  if (!activePage) return (
    <div className="flex flex-col items-center justify-center h-full gap-4">
      <p className="text-slate-500 dark:text-slate-400">Không tìm thấy dữ liệu cho batch này.</p>
      <button onClick={() => navigate('/sync')} className="btn-primary">Quay lại</button>
    </div>
  );

  const processedCount = pages.filter(p => p.status !== 'pending').length;
  const isComplete = processedCount === pages.length;

  const handleApprove = async () => {
    if (!batchId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.approveSyncPage(batchId, activePage.id);
      if (res.success) {
        const newPages = [...pages];
        newPages[activeIndex] = { ...newPages[activeIndex], status: 'approved' };
        setPages(newPages);
        if (activeIndex < pages.length - 1) setActiveIndex(activeIndex + 1);
      }
    } catch (err) {
      console.error('Failed to approve page:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleReject = async () => {
    if (rejectionReason.length < 10 || !batchId || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.rejectSyncPage(batchId, activePage.id, rejectionReason);
      if (res.success) {
        const newPages = [...pages];
        newPages[activeIndex] = { ...newPages[activeIndex], status: 'rejected', rejectionReason };
        setPages(newPages);
        setRejectionReason('');
        setShowRejectInput(false);
        if (activeIndex < pages.length - 1) setActiveIndex(activeIndex + 1);
      }
    } catch (err) {
      console.error('Failed to reject page:', err);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="h-full flex flex-col -m-4 lg:-m-6">
      <header className="bg-white dark:bg-slate-800 border-b border-slate-200 dark:border-slate-700 px-4 sm:px-6 py-4 flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2 sm:gap-4">
          <button onClick={() => navigate('/sync')} className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400 dark:text-slate-500">
            <ChevronLeft size={20} />
          </button>
          <button
            onClick={() => setIsSidebarOpen(!isSidebarOpen)}
            className="p-2 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-lg text-slate-400 dark:text-slate-500 lg:hidden"
          >
            <Menu size={20} />
          </button>
          <div>
            <div className="flex items-center gap-2 text-[10px] text-slate-500 dark:text-slate-400 font-medium">
              <span className="hidden sm:inline">Hàng đợi Sync</span>
              <ArrowRight size={10} className="hidden sm:inline" />
              <span className="truncate max-w-[100px] sm:max-w-none">Batch #{batchId}</span>
            </div>
            <h1 className="text-sm sm:text-lg font-bold text-slate-900 dark:text-white mt-0.5 truncate max-w-[150px] sm:max-w-none">
              {isProcessed ? 'Chi tiết' : 'Duyệt'}
            </h1>
          </div>
        </div>

        <div className="flex items-center gap-3 sm:gap-6">
          <div className="text-right hidden sm:block">
            <p className="text-xs text-slate-400 dark:text-slate-500">Tiến độ</p>
            <p className="text-sm font-bold text-slate-900 dark:text-white">{processedCount} / {pages.length}</p>
          </div>
          <div className="w-20 sm:w-32 h-2 bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
            <motion.div
              className="h-full bg-accent"
              initial={{ width: 0 }}
              animate={{ width: `${(processedCount / pages.length) * 100}%` }}
            />
          </div>
        </div>
      </header>

      <div className="flex-1 flex overflow-hidden relative">
        <aside className={cn(
          "w-[85vw] sm:w-80 border-r border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/50 overflow-y-auto fixed inset-y-0 left-0 z-40 transition-transform lg:relative lg:translate-x-0 bg-white dark:bg-slate-800 lg:bg-slate-50/50 lg:dark:bg-slate-800/50",
          isSidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}>
          <div className="p-4 space-y-2">
            <div className="flex items-center justify-between mb-4 lg:hidden">
              <span className="font-bold text-sm text-slate-900 dark:text-white">Danh sách trang</span>
              <button onClick={() => setIsSidebarOpen(false)} className="p-1 text-slate-400 dark:text-slate-500"><X size={20} /></button>
            </div>
            {pages.map((page, idx) => {
              const ftConfig = FILE_TYPE_ICON[page.fileType] || { icon: File, color: 'text-slate-400 bg-slate-100' };
              const FtIcon = ftConfig.icon;
              const [ftIconColor, ftBgColor] = ftConfig.color.split(' ');
              return (
                <button
                  key={page.id}
                  onClick={() => {
                    setActiveIndex(idx);
                    setIsSidebarOpen(false);
                  }}
                  className={cn(
                    "w-full text-left p-3 rounded-xl border transition-all relative group",
                    activeIndex === idx
                      ? "bg-white dark:bg-slate-800 border-accent shadow-sm ring-1 ring-accent/10 dark:ring-accent/20"
                      : "bg-transparent border-transparent hover:bg-white dark:hover:bg-slate-700 hover:border-slate-200 dark:hover:border-slate-700"
                  )}
                >
                  <div className="flex items-start gap-2.5">
                    <div className={cn("w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5", ftBgColor)}>
                      <FtIcon size={16} className={ftIconColor} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex justify-between items-start gap-1">
                        <span className={cn(
                          "text-sm font-semibold truncate block",
                          activeIndex === idx ? "text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-300"
                        )}>
                          {page.title}
                        </span>
                        <div className="shrink-0 mt-1">
                          {page.status === 'approved' && <Check size={14} className="text-success" />}
                          {page.status === 'rejected' && <X size={14} className="text-danger" />}
                          {page.status === 'pending' && <div className="w-3 h-3 rounded-full border-2 border-slate-200 dark:border-slate-700" />}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500 uppercase">{page.fileType}</span>
                        <span className="text-[10px] text-slate-300 dark:text-slate-600">·</span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">{page.fileSize}</span>
                      </div>
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </aside>

        {isSidebarOpen && (
          <div
            className="fixed inset-0 bg-slate-900/20 z-30 lg:hidden"
            onClick={() => setIsSidebarOpen(false)}
          />
        )}

        <main className="flex-1 flex flex-col bg-white dark:bg-slate-900 overflow-hidden relative">
          <div className="flex-1 overflow-y-auto p-6 sm:p-10">
            <div className="max-w-3xl mx-auto space-y-8">
              <div className="space-y-4">
                <h2 className="text-h2 font-bold text-slate-900 dark:text-white tracking-tight leading-tight">{activePage.title}</h2>

                {/* File info badge */}
                {(() => {
                  const fc = FILE_TYPE_ICON[activePage.fileType] || { icon: File, color: 'text-slate-400 bg-slate-100' };
                  const FIcon = fc.icon;
                  const [fColor, fBg] = fc.color.split(' ');
                  return (
                    <div className={cn("inline-flex items-center gap-2.5 px-3 py-2 rounded-xl border border-slate-100 dark:border-slate-700", fBg)}>
                      <FIcon size={18} className={fColor} />
                      <div className="text-xs">
                        <span className="font-semibold text-slate-700 dark:text-slate-200">{activePage.fileName}</span>
                        <span className="text-slate-400 dark:text-slate-500 ml-2">{activePage.fileSize}</span>
                      </div>
                    </div>
                  );
                })()}

                <div className="flex flex-wrap items-center gap-4 sm:gap-6 text-xs text-slate-500 dark:text-slate-400 font-medium">
                  <div className="flex items-center gap-2">
                    <div className="w-6 h-6 rounded-full bg-slate-100 dark:bg-slate-700 flex items-center justify-center text-[10px] font-bold text-slate-500 dark:text-slate-400">
                      {activePage.author.charAt(0)}
                    </div>
                    <span>{activePage.author}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Calendar size={14} className="text-slate-400 dark:text-slate-500" />
                    <span>{activePage.createdAt}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Tag size={14} className="text-slate-400 dark:text-slate-500" />
                    <div className="flex flex-wrap gap-1">
                      {activePage.tags.map(t => (
                        <span key={t} className="bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full">{t}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>

              {activePage.status === 'rejected' && activePage.rejectionReason && (
                <div className="bg-danger/5 border border-danger/10 rounded-2xl p-4 flex items-start gap-4">
                  <X className="text-danger shrink-0 mt-0.5" size={20} />
                  <div>
                    <p className="text-sm font-bold text-danger">Lý do từ chối</p>
                    <p className="text-xs text-danger/80 mt-1">{activePage.rejectionReason}</p>
                  </div>
                </div>
              )}

              {activePage.similarityScore && activePage.similarityScore > 0.8 && (
                <div className="bg-amber-50 border border-amber-100 rounded-2xl p-4 flex items-start gap-4">
                  <AlertCircle className="text-amber-500 shrink-0 mt-0.5" size={20} />
                  <div>
                    <p className="text-sm font-bold text-amber-900">Trang tương tự đã tồn tại trong Hub Tổng</p>
                    <p className="text-xs text-amber-700 mt-1">
                      Phát hiện trang <span className="font-bold underline cursor-pointer">"{activePage.similarPageTitle}"</span> với độ trùng khớp {Math.round(activePage.similarityScore * 100)}%.
                    </p>
                  </div>
                </div>
              )}

              <div className="prose prose-slate max-w-none">
                <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{activePage.content}</ReactMarkdown>
              </div>
            </div>
          </div>

          <div className="bg-white dark:bg-slate-800 border-t border-slate-200 dark:border-slate-700 p-4 sm:p-6 shrink-0">
            <div className="max-w-3xl mx-auto flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-4">
              {isProcessed ? (
                <div className="flex items-center gap-4">
                  <span className={cn(
                    "px-4 py-2 rounded-full text-xs font-semibold",
                    activePage.status === 'approved' ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
                  )}>
                    Trạng thái: {activePage.status === 'approved' ? 'Đã duyệt' : 'Đã từ chối'}
                  </span>
                </div>
              ) : (
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-4">
                  {showRejectInput ? (
                    <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                      <input
                        type="text"
                        value={rejectionReason}
                        onChange={(e) => setRejectionReason(e.target.value)}
                        placeholder="Lý do từ chối..."
                        className="input-field w-full sm:w-80"
                        autoFocus
                      />
                      <div className="flex gap-2">
                        <button
                          onClick={handleReject}
                          disabled={rejectionReason.length < 10 || actionLoading}
                          className={cn(
                            "flex-1 sm:flex-none btn-primary",
                            rejectionReason.length >= 10 && !actionLoading ? "!bg-danger !shadow-none hover:!bg-danger/90" : "!bg-slate-100 dark:!bg-slate-700 !text-slate-400 dark:!text-slate-500 cursor-not-allowed"
                          )}
                        >
                          {actionLoading ? <Loader2 size={14} className="animate-spin" /> : 'Xác nhận'}
                        </button>
                        <button onClick={() => setShowRejectInput(false)} className="btn-ghost">Hủy</button>
                      </div>
                    </div>
                  ) : (
                    <div className="flex gap-2">
                      <button
                        onClick={handleApprove}
                        disabled={activePage.status !== 'pending' || actionLoading}
                        className={cn("flex-1 sm:flex-none btn-primary", (activePage.status !== 'pending' || actionLoading) && "opacity-50 cursor-not-allowed")}
                      >
                        {actionLoading ? <Loader2 size={14} className="animate-spin mr-1" /> : null}
                        Duyệt trang
                      </button>
                      <button
                        onClick={() => setShowRejectInput(true)}
                        disabled={activePage.status !== 'pending' || actionLoading}
                        className={cn("flex-1 sm:flex-none btn-secondary text-danger border-danger/20 hover:bg-danger/5", (activePage.status !== 'pending' || actionLoading) && "opacity-50 cursor-not-allowed")}
                      >
                        Từ chối
                      </button>
                    </div>
                  )}
                </div>
              )}

              <div className="flex items-center justify-between sm:justify-end gap-4">
                {!isProcessed && <button className="btn-ghost">Duyệt tất cả</button>}
                <button
                  onClick={() => navigate('/sync')}
                  className="btn-primary"
                >
                  {isProcessed ? 'Quay lại' : 'Hoàn tất'}
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  );
};

export default SyncReview;
