import React, { useState, useMemo, useEffect } from 'react';
import { api, type SyncBatchAPI, type HubAPI } from '../services/api';
import type { SyncBatch, FileType } from '../types';
import { cn } from '../lib/utils';
import {
  RefreshCw, ArrowRight, CheckCircle2, Clock, XCircle, Eye,
  FileText, File, FileSpreadsheet, Presentation, FileCode,
  Image, Globe, Database as TableIcon, HardDrive, Loader2
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { motion } from 'motion/react';
import Pagination from '../components/Pagination';

const FILE_TYPE_CONFIG: Record<FileType, { icon: React.ElementType; color: string; label: string }> = {
  pdf: { icon: FileText, color: 'text-red-500 bg-red-50', label: 'PDF' },
  docx: { icon: File, color: 'text-blue-600 bg-blue-50', label: 'DOCX' },
  xlsx: { icon: FileSpreadsheet, color: 'text-emerald-600 bg-emerald-50', label: 'XLSX' },
  pptx: { icon: Presentation, color: 'text-orange-500 bg-orange-50', label: 'PPTX' },
  txt: { icon: FileText, color: 'text-slate-500 bg-slate-100', label: 'TXT' },
  md: { icon: FileCode, color: 'text-violet-600 bg-violet-50', label: 'MD' },
  jpg: { icon: Image, color: 'text-pink-500 bg-pink-50', label: 'JPG' },
  png: { icon: Image, color: 'text-teal-500 bg-teal-50', label: 'PNG' },
  csv: { icon: TableIcon, color: 'text-green-600 bg-green-50', label: 'CSV' },
  html: { icon: Globe, color: 'text-amber-600 bg-amber-50', label: 'HTML' },
};

const FileTypeBadge = ({ type, count }: { type: FileType; count: number }) => {
  const config = FILE_TYPE_CONFIG[type];
  if (!config) return null;
  const Icon = config.icon;
  const [iconColor, bgColor] = config.color.split(' ');
  return (
    <span className={cn("inline-flex items-center gap-1 px-1.5 py-0.5 rounded-md text-[10px] font-semibold", bgColor, iconColor)}>
      <Icon size={11} />
      {count} {config.label}
    </span>
  );
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function timeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  if (diffMins < 1) return 'Vừa xong';
  if (diffMins < 60) return `${diffMins} phút trước`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} giờ trước`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays < 30) return `${diffDays} ngày trước`;
  return date.toLocaleDateString('vi-VN');
}

function mapBatch(b: SyncBatchAPI): SyncBatch {
  const status: SyncBatch['status'] = b.status === 'pending' ? 'pending' : 'processed';
  return {
    id: b.id,
    hubId: b.hub_id,
    hubName: b.hub_name,
    pageCount: b.page_count,
    submittedAt: timeAgo(b.submitted_at),
    submittedBy: b.submitted_by_name,
    status,
    filesSummary: b.files_summary as SyncBatch['filesSummary'],
    totalSize: formatBytes(b.total_size),
    processedCount: status === 'processed' ? { approved: b.approved_count, rejected: b.rejected_count } : undefined,
  };
}

const SyncQueue = () => {
  const [activeTab, setActiveTab] = useState<'all' | 'pending' | 'processed'>('all');
  const [currentPage, setCurrentPage] = useState(1);
  const [batches, setBatches] = useState<SyncBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [totalBatches, setTotalBatches] = useState(0);
  const itemsPerPage = 10;

  useEffect(() => {
    let cancelled = false;
    const fetchBatches = async () => {
      setLoading(true);
      try {
        const statusParam = activeTab === 'pending' ? 'pending' : activeTab === 'processed' ? 'completed' : undefined;
        const res = await api.getSyncBatches({ status: statusParam, page: currentPage, per_page: itemsPerPage });
        if (cancelled) return;
        if (res.success && res.data) {
          setBatches(res.data.map(mapBatch));
          setTotalBatches(res.meta?.total ?? res.data.length);
        }
      } catch (err) {
        console.error('Failed to fetch sync batches:', err);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchBatches();
    // Auto-refresh every 30s
    const interval = setInterval(fetchBatches, 30_000);
    return () => { cancelled = true; clearInterval(interval); };
  }, [activeTab, currentPage]);

  // Fetch counts for tabs
  const [tabCounts, setTabCounts] = useState({ all: 0, pending: 0, processed: 0 });
  useEffect(() => {
    const fetchCounts = async () => {
      try {
        const [allRes, statsRes] = await Promise.all([
          api.getSyncBatches({ per_page: 1 }),
          api.getSyncStats(),
        ]);
        const allCount = allRes.meta?.total ?? 0;
        const pendingCount = statsRes.success && statsRes.data ? statsRes.data.pending_batches : 0;
        setTabCounts({
          all: allCount,
          pending: pendingCount,
          processed: allCount - pendingCount,
        });
      } catch (err) {
        console.error('Failed to fetch tab counts:', err);
      }
    };
    fetchCounts();
  }, [batches]);

  const totalPages = Math.ceil(totalBatches / itemsPerPage);

  const handleTabChange = (tab: 'all' | 'pending' | 'processed') => {
    setActiveTab(tab);
    setCurrentPage(1);
  };

  const tabs = [
    { id: 'all' as const, label: 'Tất cả', count: tabCounts.all },
    { id: 'pending' as const, label: 'Chờ duyệt', count: tabCounts.pending },
    { id: 'processed' as const, label: 'Đã xử lý', count: tabCounts.processed },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Hàng đợi Sync</h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Quản lý các yêu cầu đồng bộ tri thức từ Hub Dự Án</p>
        </div>
        <div className="flex items-center gap-2 bg-slate-100 dark:bg-slate-700 px-3 py-1.5 rounded-full text-xs text-slate-500 dark:text-slate-400">
          <RefreshCw size={12} className="animate-spin-slow" />
          Tự động cập nhật: 30s
        </div>
      </div>

      <div className="glass-card overflow-hidden">
        {/* Tabs */}
        <div className="flex border-b border-slate-200/50 dark:border-slate-700/50 px-2 pt-2 gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => handleTabChange(tab.id)}
              className={cn(
                "relative px-4 py-2.5 text-sm font-medium transition-colors rounded-t-lg",
                activeTab === tab.id ? "text-brand-indigo" : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              )}
            >
              <span className="flex items-center gap-2">
                {tab.label}
                <span className={cn(
                  "text-[10px] font-bold px-1.5 py-0.5 rounded-full",
                  activeTab === tab.id
                    ? tab.id === 'pending' ? "bg-brand-indigo/10 dark:bg-brand-indigo/20 text-brand-indigo" : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                    : "bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500"
                )}>
                  {tab.count}
                </span>
              </span>
              {activeTab === tab.id && (
                <motion.div layoutId="syncTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-indigo" />
              )}
            </button>
          ))}
        </div>

        {/* Table */}
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 size={24} className="animate-spin text-brand-indigo" />
              <span className="ml-3 text-sm text-slate-500 dark:text-slate-400">Đang tải dữ liệu...</span>
            </div>
          ) : (
            <table className="w-full text-left border-collapse min-w-[850px]">
              <thead>
                <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Hub nguồn</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tệp tin</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Dung lượng</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Thời gian gửi</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Admin gửi</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                  <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-right">Thao tác</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
                {batches.map((batch) => (
                  <tr key={batch.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors group">
                    <td className="px-5 py-4">
                      <span className="font-bold text-sm text-slate-900 dark:text-white">{batch.hubName}</span>
                    </td>
                    <td className="px-5 py-4">
                      <div className="space-y-1.5">
                        <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{batch.pageCount} tệp</span>
                        <div className="flex flex-wrap gap-1">
                          {Object.entries(batch.filesSummary)
                            .sort(([, a], [, b]) => (b as number) - (a as number))
                            .map(([type, count]) => (
                              <FileTypeBadge key={type} type={type as FileType} count={count as number} />
                            ))
                          }
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400">
                        <HardDrive size={13} className="text-slate-400 dark:text-slate-500" />
                        {batch.totalSize}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{batch.submittedAt}</td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{batch.submittedBy}</td>
                    <td className="px-5 py-4">
                      {batch.status === 'pending' ? (
                        <span className="inline-flex items-center gap-1.5 text-[10px] font-semibold text-brand-indigo bg-brand-indigo/10 dark:bg-brand-indigo/20 px-2 py-0.5 rounded-full">
                          <Clock size={10} /> Chờ duyệt
                        </span>
                      ) : (
                        <div className="flex items-center gap-2">
                          <span className="inline-flex items-center gap-1 text-xs text-success font-medium">
                            <CheckCircle2 size={14} /> {batch.processedCount?.approved}
                          </span>
                          <span className="inline-flex items-center gap-1 text-xs text-danger font-medium">
                            <XCircle size={14} /> {batch.processedCount?.rejected}
                          </span>
                        </div>
                      )}
                    </td>
                    <td className="px-5 py-4 text-right">
                      <Link
                        to={`/sync/review/${batch.id}`}
                        className={cn(
                          "inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold transition-all",
                          batch.status === 'pending'
                            ? "text-brand-indigo bg-brand-indigo/10 dark:bg-brand-indigo/20 hover:bg-brand-indigo/20"
                            : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 bg-slate-100 dark:bg-slate-700"
                        )}
                      >
                        {batch.status === 'pending' ? (
                          <>Duyệt <ArrowRight size={14} /></>
                        ) : (
                          <><Eye size={14} /> Chi tiết</>
                        )}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={totalBatches}
          itemsPerPage={itemsPerPage}
        />
      </div>
    </div>
  );
};

export default SyncQueue;
