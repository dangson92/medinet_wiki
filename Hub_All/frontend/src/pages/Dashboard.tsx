import React, { useState, useEffect, useMemo } from 'react';
import type { Hub, AuditLogEntry } from '../types';
import { cn } from '../lib/utils';
import { motion } from 'motion/react';
import {
  ArrowRight, ExternalLink, Clock, User, Activity, RefreshCw, Sparkles,
  TrendingUp, Database, BookOpen, Users, HardDrive, CheckCircle2, XCircle,
  FileText, File, FileSpreadsheet, Presentation, FileCode, Image, Globe,
  Database as TableIcon, ArrowUpRight, BarChart3, Loader2
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, type HubAPI, type AuditLogAPI } from '../services/api';

/* ── Map API Hub to frontend Hub type ── */
function mapHubAPIToHub(h: HubAPI, docCount = 0, userCount = 0, pendingSync = 0): Hub {
  const now = new Date();
  const updated = new Date(h.updated_at);
  const diffMs = now.getTime() - updated.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  let lastUpdate = '';
  if (diffDays > 0) lastUpdate = `${diffDays} ngày trước`;
  else if (diffHours > 0) lastUpdate = `${diffHours} giờ trước`;
  else if (diffMins > 0) lastUpdate = `${diffMins} phút trước`;
  else lastUpdate = 'Vừa xong';

  return {
    id: h.id,
    name: h.name,
    code: h.code,
    subdomain: h.subdomain,
    pages: docCount,
    users: userCount,
    lastUpdate,
    status: h.status === 'active' ? 'active' : 'inactive',
    pendingSync,
    createdAt: h.created_at,
  };
}

/* ── Map AuditLogAPI to frontend AuditLogEntry ── */
function mapAuditLogToFE(log: AuditLogAPI): AuditLogEntry {
  const now = new Date();
  const ts = new Date(log.timestamp);
  const diffMs = now.getTime() - ts.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  let timestamp = '';
  if (diffDays > 0) timestamp = `${diffDays} ngày trước`;
  else if (diffHours > 0) timestamp = `${diffHours} giờ trước`;
  else if (diffMins > 0) timestamp = `${diffMins} phút trước`;
  else timestamp = 'Vừa xong';

  return {
    id: log.id,
    timestamp,
    user: log.user_name || (log.is_ai ? 'AI Agent' : 'Hệ thống'),
    isAI: log.is_ai,
    action: log.action as AuditLogEntry['action'],
    target: log.target || '—',
    hub: log.hub_name || '—',
    ip: log.ip_address || '—',
  };
}

/* ── File type config ── */
type FileType = 'pdf' | 'docx' | 'xlsx' | 'pptx' | 'txt' | 'md' | 'jpg' | 'png' | 'csv' | 'html';

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

/* ── Stat Card ── */
const StatCard = ({ label, value, subValue, highlight, icon: Icon, trend, to }: {
  label: string; value: string; subValue?: string; highlight?: boolean;
  icon?: React.ElementType; trend?: string; to?: string;
}) => {
  const inner = (
    <div className={cn(
      "glass-card p-5 sm:p-6 flex flex-col justify-between group relative overflow-hidden h-full transition-all",
      highlight && "border-brand-indigo/30 bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08]",
      to && "hover:shadow-md hover:border-brand-indigo/20 cursor-pointer"
    )}>
      {highlight && <div className="absolute top-0 right-0 w-24 h-24 bg-brand-indigo/5 rounded-full -mr-12 -mt-12" />}
      <div className="flex justify-between items-start relative z-10">
        <span className="text-xs text-slate-400 dark:text-slate-500 font-medium">{label}</span>
        {Icon && <Icon size={16} className={cn("text-slate-300 dark:text-slate-600 group-hover:text-brand-indigo transition-colors", highlight && "text-brand-indigo")} />}
      </div>
      <div className="mt-3 flex items-baseline gap-2 relative z-10">
        <span className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white tracking-tight">{value}</span>
        {subValue && <span className="text-xs font-medium text-slate-500 dark:text-slate-400">{subValue}</span>}
      </div>
      {trend && (
        <div className="mt-2 flex items-center gap-1 text-[10px] font-bold text-success relative z-10">
          <TrendingUp size={10} />
          <span>{trend} so với tháng trước</span>
        </div>
      )}
      {to && (
        <div className="absolute bottom-3 right-3 opacity-0 group-hover:opacity-100 transition-opacity">
          <ArrowUpRight size={14} className="text-brand-indigo" />
        </div>
      )}
    </div>
  );
  if (to) return <Link to={to} className="block h-full">{inner}</Link>;
  return inner;
};

/* ── Dashboard ── */
const Dashboard = () => {
  const [aiInsight, setAiInsight] = useState<string>('');
  const [isAiLoading, setIsAiLoading] = useState(false);
  const [hubs, setHubs] = useState<Hub[]>([]);
  const [hubsLoading, setHubsLoading] = useState(true);

  // New API state
  const [recentLogs, setRecentLogs] = useState<AuditLogEntry[]>([]);
  const [logsLoading, setLogsLoading] = useState(true);
  const [syncStats, setSyncStats] = useState<{ pending_batches: number; pending_pages: number }>({ pending_batches: 0, pending_pages: 0 });
  const [totalKnowledge, setTotalKnowledge] = useState(0);

  // Fetch hubs with real document/user counts
  useEffect(() => {
    const fetchHubs = async () => {
      setHubsLoading(true);
      try {
        const res = await api.getHubs();
        if (res.success && res.data) {
          // Fetch per-hub doc counts and user counts in parallel
          const hubData = await Promise.all(
            res.data.map(async (h) => {
              const [docRes, userRes] = await Promise.all([
                api.getDocuments({ hub_id: h.id, page: 1, per_page: 1 }).catch(() => null),
                api.getUsers({ hub_id: h.id, page: 1, per_page: 1 }).catch(() => null),
              ]);
              const docCount = docRes?.meta?.total ?? 0;
              const userCount = userRes?.meta?.total ?? 0;
              return mapHubAPIToHub(h, docCount, userCount, 0);
            })
          );
          setHubs(hubData);
        }
      } catch (err) {
        console.error('Failed to fetch hubs:', err);
      } finally {
        setHubsLoading(false);
      }
    };
    fetchHubs();
  }, []);

  // Fetch audit logs, sync stats, and documents count
  useEffect(() => {
    const fetchAuditLogs = async () => {
      setLogsLoading(true);
      try {
        const res = await api.getAuditLogs({ per_page: 6 });
        if (res.success && res.data) {
          setRecentLogs(res.data.map(mapAuditLogToFE));
        }
      } catch (err) {
        console.error('Failed to fetch audit logs:', err);
      } finally {
        setLogsLoading(false);
      }
    };

    const fetchSyncStats = async () => {
      try {
        const res = await api.getSyncStats();
        if (res.success && res.data) {
          setSyncStats(res.data);
        }
      } catch (err) {
        console.error('Failed to fetch sync stats:', err);
      }
    };

    const fetchDocuments = async () => {
      try {
        const res = await api.getDocuments({ status: 'completed', page: 1, per_page: 1 });
        if (res.success && res.meta) {
          setTotalKnowledge(res.meta.total);
        }
      } catch (err) {
        console.error('Failed to fetch documents count:', err);
      }
    };

    fetchAuditLogs();
    fetchSyncStats();
    fetchDocuments();
  }, []);

  // Computed stats from fetched hubs + API data
  const stats = useMemo(() => {
    const activeHubs = hubs.filter(h => h.status === 'active');
    const totalPages = hubs.reduce((sum, h) => sum + h.pages, 0);
    const totalUsers = hubs.reduce((sum, h) => sum + h.users, 0);

    return {
      activeHubs: activeHubs.length,
      totalHubs: hubs.length,
      totalPages,
      totalUsers,
      pendingBatches: syncStats.pending_batches,
      pendingFileCount: syncStats.pending_pages,
      totalKnowledge,
    };
  }, [hubs, syncStats, totalKnowledge]);

  const getActionLabel = (action: string) => {
    switch (action) {
      case 'UPDATE': return 'cập nhật';
      case 'CREATE': return 'tạo mới';
      case 'DELETE': return 'xóa';
      case 'SYNC': return 'đồng bộ';
      case 'APPROVE_SYNC': return 'duyệt sync';
      case 'REJECT_SYNC': return 'từ chối sync';
      case 'LOGIN': return 'đăng nhập';
      case 'MCP_READ': return 'đọc dữ liệu';
      case 'MCP_WRITE': return 'ghi dữ liệu';
      default: return 'thực hiện';
    }
  };

  const fetchAiInsight = async () => {
    setIsAiLoading(true);
    try {
      const prompt = `Dựa trên dữ liệu hệ thống Hub Tổng Medinet Wiki, hãy đưa ra 1 nhận xét ngắn gọn (tối đa 2 câu) về tình trạng:
      - Tổng tri thức Wiki: ${stats.totalPages} trang trên ${stats.activeHubs} Hub hoạt động
      - Tổng user: ${stats.totalUsers} người
      - ${stats.pendingBatches} batch sync đang chờ duyệt (${stats.pendingFileCount} tệp)
      - ${stats.totalKnowledge} tri thức đã nạp vào RAG
      Hãy trả lời bằng tiếng Việt, phong cách chuyên nghiệp, tích cực.`;

      const res = await api.aiChat([{ role: 'user', content: prompt }]);
      if (res.success && res.data?.response) {
        setAiInsight(res.data.response);
      } else {
        setAiInsight(`Hệ thống đang hoạt động ổn định với ${stats.totalPages} trang tri thức. Có ${stats.pendingBatches} batch sync cần được duyệt.`);
      }
    } catch {
      setAiInsight(`Hệ thống hoạt động ổn định với ${stats.activeHubs} Hub đang kết nối. Hiện có ${stats.pendingBatches} batch sync (${stats.pendingFileCount} tệp) đang chờ duyệt từ các Hub con.`);
    } finally {
      setIsAiLoading(false);
    }
  };

  useEffect(() => {
    fetchAiInsight();
  }, []);

  return (
    <div className="space-y-8">
      {/* AI Insight Banner */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="glass-card p-4 border-brand-indigo/20 bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] flex flex-col sm:flex-row items-start sm:items-center gap-4"
      >
        <div className="w-10 h-10 rounded-full bg-brand-indigo flex items-center justify-center text-white shadow-lg shrink-0">
          <Sparkles size={20} />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-brand-indigo">AI Insights</span>
            {isAiLoading && <span className="text-[10px] text-slate-400 dark:text-slate-500 italic">Đang phân tích...</span>}
          </div>
          <p className="text-sm text-slate-700 dark:text-slate-200 font-medium line-clamp-2">
            {isAiLoading ? 'Gemini đang tổng hợp dữ liệu hệ thống cho bạn...' : aiInsight}
          </p>
        </div>
        <button
          onClick={fetchAiInsight}
          className="p-2 hover:bg-white dark:hover:bg-slate-700 rounded-lg text-slate-400 dark:text-slate-500 hover:text-brand-indigo transition-all self-end sm:self-center"
          title="Làm mới nhận xét"
        >
          <RefreshCw size={16} className={cn(isAiLoading && "animate-spin")} />
        </button>
      </motion.div>

      {/* Stats */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 sm:gap-6 items-stretch">
        <StatCard
          label="Hub hoạt động"
          value={String(stats.activeHubs)}
          subValue={`/ ${stats.totalHubs} Hub`}
          icon={Database}
          to="/registry"
        />
        <StatCard
          label="Tổng tri thức"
          value={stats.totalPages.toLocaleString()}
          subValue="trang"
          icon={BookOpen}
          to="/documents"
        />
        <StatCard
          label="Người dùng"
          value={String(stats.totalUsers)}
          subValue="người"
          icon={Users}
          to="/users"
        />
        <StatCard
          label="Tri thức RAG"
          value={String(stats.totalKnowledge)}
          subValue="đã nạp"
          icon={BarChart3}
          to="/documents"
        />
        <StatCard
          label="Sync chờ duyệt"
          value={String(stats.pendingBatches)}
          subValue={`batch · ${stats.pendingFileCount} tệp`}
          highlight
          icon={RefreshCw}
          to="/sync"
        />
      </div>

      {/* Hub Overview */}
      <div className="glass-card overflow-hidden">
        <div className="p-5 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-slate-900 dark:text-white tracking-tight">Tổng quan Hub</h2>
          <Link to="/registry" className="btn-ghost">
            Xem Registry
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[750px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tên Hub</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Subdomain</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tri thức</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Người dùng</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Cập nhật</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Sync chờ</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {hubsLoading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-400 dark:text-slate-500">
                      <Loader2 size={18} className="animate-spin" />
                      <span className="text-sm">Đang tải dữ liệu Hub...</span>
                    </div>
                  </td>
                </tr>
              ) : hubs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-400 dark:text-slate-500">
                    Chưa có Hub nào trong hệ thống
                  </td>
                </tr>
              ) : hubs.map((hub) => (
                <tr key={hub.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors group">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-2">
                      <div className={cn(
                        "w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold shrink-0",
                        hub.status === 'active' ? "bg-brand-indigo/10 dark:bg-brand-indigo/20 text-brand-indigo" : "bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500"
                      )}>
                        {hub.name.charAt(0)}
                      </div>
                      <div>
                        <span className={cn("font-semibold text-sm", hub.status === 'inactive' ? "text-slate-400 dark:text-slate-500 italic" : "text-slate-900 dark:text-white")}>
                          {hub.name}
                        </span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500 block font-mono">{hub.code}</span>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className={cn("text-xs font-mono", hub.status === 'inactive' ? "text-slate-400 dark:text-slate-500 line-through" : "text-accent")}>
                      {hub.subdomain}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">{hub.pages}</span>
                    <span className="text-xs text-slate-400 dark:text-slate-500 ml-1">trang</span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1.5">
                      <Users size={13} className="text-slate-400 dark:text-slate-500" />
                      <span className="text-sm text-slate-600 dark:text-slate-300">{hub.users}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{hub.lastUpdate}</td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "badge",
                      hub.status === 'active' ? "badge-success" : "badge-slate"
                    )}>
                      {hub.status === 'active' ? 'Hoạt động' : 'Vô hiệu'}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    {hub.pendingSync > 0 ? (
                      <Link
                        to="/sync"
                        className="badge badge-accent hover:bg-accent hover:text-white transition-all flex items-center gap-1 w-fit"
                      >
                        {hub.pendingSync} tệp
                        <ArrowRight size={10} />
                      </Link>
                    ) : (
                      <span className="text-xs text-slate-300 dark:text-slate-600">Không có</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Bottom Grid: Sync Queue + Activity */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sync chờ duyệt */}
        <div className="glass-card flex flex-col">
          <div className="p-5 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-semibold text-slate-900 dark:text-white tracking-tight">Sync chờ duyệt</h2>
              <span className="bg-brand-indigo/10 dark:bg-brand-indigo/20 text-brand-indigo text-[10px] font-bold px-2 py-0.5 rounded-full">
                {stats.pendingBatches}
              </span>
            </div>
            <Link to="/sync" className="text-accent text-xs font-medium hover:underline flex items-center gap-1">
              Hàng đợi <ArrowRight size={14} />
            </Link>
          </div>
          <div className="p-4 flex-1 space-y-3">
            {stats.pendingBatches > 0 ? (
              <div className="h-full flex flex-col items-center justify-center text-slate-500 dark:text-slate-400 space-y-2 py-8">
                <RefreshCw size={32} className="opacity-30" />
                <p className="text-sm font-medium">{stats.pendingBatches} batch ({stats.pendingFileCount} tệp) đang chờ duyệt</p>
                <Link
                  to="/sync"
                  className="text-accent text-xs font-bold hover:underline flex items-center gap-1 mt-2"
                >
                  Xem hàng đợi <ArrowRight size={12} />
                </Link>
              </div>
            ) : (
              <div className="h-full flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 space-y-2 py-12">
                <CheckCircle2 size={32} className="opacity-20" />
                <p className="text-sm font-medium">Tất cả đã được duyệt</p>
              </div>
            )}
          </div>
        </div>

        {/* Hoạt động gần đây */}
        <div className="glass-card flex flex-col">
          <div className="p-5 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
            <h2 className="text-lg font-semibold text-slate-900 dark:text-white tracking-tight">Hoạt động gần đây</h2>
            <Link to="/logs" className="text-accent text-xs font-medium hover:underline flex items-center gap-1">
              Xem tất cả <ArrowRight size={14} />
            </Link>
          </div>
          <div className="p-4 flex-1">
            {logsLoading ? (
              <div className="flex items-center justify-center gap-2 text-slate-400 dark:text-slate-500 py-12">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">Đang tải...</span>
              </div>
            ) : recentLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-slate-400 dark:text-slate-500 py-12">
                <Activity size={32} className="opacity-20 mb-2" />
                <p className="text-sm">Chưa có hoạt động nào</p>
              </div>
            ) : (
              <div className="space-y-1">
                {recentLogs.map((log) => (
                  <div key={log.id} className="flex gap-3 p-2.5 rounded-lg hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors">
                    <div className="shrink-0 mt-0.5">
                      <div className={cn(
                        "w-7 h-7 rounded-full flex items-center justify-center",
                        log.isAI ? "bg-brand-purple/10 dark:bg-brand-purple/20 text-brand-purple" : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                      )}>
                        {log.isAI ? <Activity size={13} /> : <User size={13} />}
                      </div>
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed">
                        <span className={cn("font-bold", log.isAI && "text-brand-purple")}>
                          {log.user}
                        </span>
                        {' '}{getActionLabel(log.action)}{' '}
                        {log.target !== '—' && <span className="font-semibold text-slate-900 dark:text-white">{log.target}</span>}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">{log.timestamp}</span>
                        <span className="text-[10px] text-slate-300 dark:text-slate-600">·</span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">{log.hub}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
