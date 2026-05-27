import React, { useState, useEffect, useMemo } from 'react';
import type { Hub, AuditLogEntry } from '../types';
import { cn, getHubUrl, extractAuditTargetName } from '../lib/utils';
import { motion } from 'motion/react';
import {
  ArrowRight, ExternalLink, Clock, User, Activity, RefreshCw, Sparkles,
  Database, BookOpen, Users, CheckCircle2, Trash2, MoreVertical,
  FileText, File, FileSpreadsheet, Presentation, FileCode, Image, Globe,
  Database as TableIcon, BarChart3, Loader2
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { api, type HubAPI, type AuditLogAPI, type SyncBatchAPI } from '../services/api';

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
    // Ưu tiên payload.document_name / .email / .name etc thay vì UUID target_id
    // (extractAuditTargetName shared với AuditLog.tsx — lib/utils.ts).
    target: extractAuditTargetName(log.target || '', log.payload) || '—',
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

/* ── Stat Card (mẫu giao-dien-mau §"Key Metrics Summary") ── */
type StatBadgeTone = 'success' | 'indigo' | 'amber' | 'slate';

const StatCard = ({
  label,
  value,
  subValue,
  icon: Icon,
  iconTone = 'indigo',
  badge,
  badgeTone = 'success',
  to,
}: {
  label: string;
  value: string;
  subValue?: string;
  icon?: React.ElementType;
  iconTone?: 'indigo' | 'secondary' | 'tertiary';
  badge?: string;
  badgeTone?: StatBadgeTone;
  to?: string;
}) => {
  const iconToneCls = {
    indigo: 'text-primary',
    secondary: 'text-sky-600 dark:text-sky-400',
    tertiary: 'text-fuchsia-600 dark:text-fuchsia-400',
  }[iconTone];

  const badgeToneCls = {
    success: 'text-emerald-600 dark:text-emerald-400',
    indigo: 'text-primary',
    amber: 'text-amber-600 dark:text-amber-400',
    slate: 'text-on-surface-variant dark:text-slate-400',
  }[badgeTone];

  const inner = (
    <div className={cn(
      "m3-card p-5 group h-full transition-all",
      to && "hover:shadow-md hover:border-primary/20 cursor-pointer"
    )}>
      <div className="flex items-center justify-between mb-4">
        {Icon && (
          <div className={cn(
            "w-8 h-8 rounded-lg flex items-center justify-center border border-outline-variant dark:border-slate-700 bg-surface-container-low dark:bg-slate-800/50",
            iconToneCls
          )}>
            <Icon size={18} />
          </div>
        )}
        {badge && (
          <span className={cn("text-[11px] font-bold flex items-center gap-1", badgeToneCls)}>
            {badgeTone === 'success' && <span className="w-1.5 h-1.5 bg-emerald-500 rounded-full" />}
            {badge}
          </span>
        )}
      </div>
      <h4 className="text-[10px] uppercase tracking-wider font-bold text-outline dark:text-slate-500 mb-1">{label}</h4>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold text-on-surface dark:text-white tracking-tight">{value}</span>
        {subValue && <span className="text-xs font-medium text-on-surface-variant dark:text-slate-400">{subValue}</span>}
      </div>
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
  const [pendingBatches, setPendingBatches] = useState<SyncBatchAPI[]>([]);
  const [pendingBatchesLoading, setPendingBatchesLoading] = useState(true);
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

    const fetchPendingBatches = async () => {
      setPendingBatchesLoading(true);
      try {
        const res = await api.getSyncBatches({ status: 'pending', per_page: 5 });
        if (res.success && res.data) {
          setPendingBatches(res.data);
        }
      } catch (err) {
        console.error('Failed to fetch pending sync batches:', err);
      } finally {
        setPendingBatchesLoading(false);
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
    fetchPendingBatches();
    fetchDocuments();
  }, []);

  // Helper format file size
  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  // Helper relative time
  const timeAgo = (iso: string): string => {
    const diff = Date.now() - new Date(iso).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins} phút trước`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours} giờ trước`;
    const days = Math.floor(hours / 24);
    return `${days} ngày trước`;
  };

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

  // Mapping action code BE emit → tiếng Việt người đọc được. Action thật từ DB
  // (`SELECT DISTINCT action FROM audit_logs`) + grep `action=` toàn repo:
  //   document_delete · document.version.create · document.version.restore
  //   user.create · user.delete · user.password_reset
  //   hub.create · hub.update
  //   sync.replay · security.hub_isolation_violation · migration.role_seed
  // Generic UPPERCASE legacy (UPDATE/CREATE/DELETE/...) giữ lại fallback M2.
  const getActionLabel = (action: string) => {
    switch (action) {
      // Document lifecycle
      case 'document_delete': return 'xoá tài liệu';
      case 'document.version.create': return 'tạo phiên bản tài liệu';
      case 'document.version.restore': return 'khôi phục phiên bản tài liệu';
      // User lifecycle
      case 'user.create': return 'tạo user';
      case 'user.delete': return 'xoá user';
      case 'user.password_reset': return 'reset mật khẩu user';
      // Hub lifecycle
      case 'hub.create': return 'tạo hub';
      case 'hub.update': return 'cập nhật hub';
      // Sync + security + migration
      case 'sync.replay': return 'replay sync';
      case 'security.hub_isolation_violation': return 'vi phạm hub isolation';
      case 'migration.role_seed': return 'seed role hub_admin';
      // Legacy UPPERCASE (giữ tương thích nếu còn audit row cũ)
      case 'UPDATE': return 'cập nhật';
      case 'CREATE': return 'tạo mới';
      case 'DELETE': return 'xoá';
      case 'SYNC': return 'đồng bộ';
      case 'APPROVE_SYNC': return 'duyệt sync';
      case 'REJECT_SYNC': return 'từ chối sync';
      case 'LOGIN': return 'đăng nhập';
      case 'MCP_READ': return 'đọc dữ liệu';
      case 'MCP_WRITE': return 'ghi dữ liệu';
      default: return action;  // hiện raw thay vì 'thực hiện' để forensic dễ debug
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
    <div className="space-y-6">
      {/* AI Insight Banner — mẫu giao-dien-mau dashboard §"AI Insight Banner" */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="m3-card p-5 sm:p-6 relative overflow-hidden"
      >
        <div className="flex items-start gap-4">
          <div className="w-10 h-10 flex items-center justify-center shrink-0">
            <img src="/mascot.png" alt="AI Mascot" className="w-10 h-10 object-contain" />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex justify-between items-center mb-1 gap-2">
              <h3 className="font-bold text-base text-on-surface dark:text-white flex items-center gap-1.5">
                {isAiLoading ? 'Gemini đang tổng hợp dữ liệu' : 'AI Insights'}
                {isAiLoading && (
                  <span className="flex gap-1 ml-1">
                    <span className="w-1 h-1 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.1s' }} />
                    <span className="w-1 h-1 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.2s' }} />
                    <span className="w-1 h-1 bg-primary rounded-full animate-bounce" style={{ animationDelay: '0.3s' }} />
                  </span>
                )}
              </h3>
              <div className="flex items-center gap-2 shrink-0">
                <span className="text-[10px] font-bold text-outline dark:text-slate-500 uppercase tracking-widest">Live Insight</span>
                <button
                  onClick={fetchAiInsight}
                  className="p-1 hover:bg-surface-container-low dark:hover:bg-slate-700 rounded text-outline dark:text-slate-500 hover:text-primary transition-all"
                  title="Làm mới nhận xét"
                >
                  <RefreshCw size={14} className={cn(isAiLoading && "animate-spin")} />
                </button>
              </div>
            </div>
            <p className="text-sm text-on-surface-variant dark:text-slate-300 max-w-4xl leading-relaxed">
              {isAiLoading
                ? 'Đang phân tích dữ liệu hệ thống — vui lòng chờ trong giây lát...'
                : aiInsight}
            </p>
          </div>
        </div>
      </motion.div>

      {/* Stats — 4 cards (mẫu giao-dien-mau dashboard §"Key Metrics Summary") */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 sm:gap-6 items-stretch">
        <StatCard
          label="Hub hoạt động"
          value={`${stats.activeHubs}/${stats.totalHubs}`}
          subValue="Hub"
          icon={Database}
          iconTone="secondary"
          badge={stats.totalHubs > 0 ? `${Math.round((stats.activeHubs / stats.totalHubs) * 100)}%` : undefined}
          badgeTone="success"
          to="/registry"
        />
        <StatCard
          label="Tổng tri thức"
          value={stats.totalPages.toLocaleString()}
          subValue="trang nội dung"
          icon={BookOpen}
          iconTone="indigo"
          to="/documents"
        />
        <StatCard
          label="Người dùng"
          value={String(stats.totalUsers)}
          subValue="nhân sự"
          icon={Users}
          iconTone="tertiary"
          to="/users"
        />
        <StatCard
          label="Tri thức RAG"
          value={String(stats.totalKnowledge)}
          subValue="đã nạp vector"
          icon={BarChart3}
          iconTone="indigo"
          badge={stats.pendingBatches > 0 ? `${stats.pendingBatches} chờ` : undefined}
          badgeTone={stats.pendingBatches > 0 ? 'indigo' : 'success'}
          to="/documents"
        />
      </div>

      {/* Main Layout Grid — mẫu giao-dien-mau dashboard §"Main Layout Grid" (12-col: center 8 + right 4) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
      {/* Center column: Hub Overview + Sync chờ duyệt (col-span-8) */}
      <div className="lg:col-span-8 space-y-6">
      {/* Hub Overview — mẫu giao-dien-mau dashboard §"Tổng quan Hub" (5 cột tinh giản) */}
      <div className="m3-card overflow-hidden">
        <div className="p-5 border-b border-outline-variant dark:border-slate-700 flex justify-between items-center">
          <h2 className="font-bold text-body-lg text-on-surface dark:text-white">Tổng quan Hub</h2>
          <Link to="/registry" className="btn-ghost">
            Xem Registry
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[640px]">
            <thead>
              <tr className="bg-surface-container-low/50 dark:bg-slate-800/50 border-b border-outline-variant dark:border-slate-700">
                <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">Tên Hub</th>
                <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">Tri thức</th>
                <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">Người dùng</th>
                <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">Trạng thái</th>
                <th className="px-5 py-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">Sync</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant dark:divide-slate-700">
              {hubsLoading ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-outline dark:text-slate-500">
                      <Loader2 size={18} className="animate-spin" />
                      <span className="text-sm">Đang tải dữ liệu Hub...</span>
                    </div>
                  </td>
                </tr>
              ) : hubs.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-5 py-12 text-center text-sm text-outline dark:text-slate-500">
                    Chưa có Hub nào trong hệ thống
                  </td>
                </tr>
              ) : hubs.map((hub) => (
                <tr key={hub.id} className="hover:bg-surface-container-low/50 dark:hover:bg-slate-700/50 transition-colors group">
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-9 h-9 rounded-lg flex items-center justify-center text-xs font-bold shrink-0 shadow-sm",
                        hub.status === 'active'
                          ? "bg-primary/10 dark:bg-primary/20 text-primary border border-primary/20"
                          : "bg-surface-container-low dark:bg-slate-700 text-outline dark:text-slate-500"
                      )}>
                        {hub.name.charAt(0)}
                      </div>
                      <div className="min-w-0">
                        <p className={cn(
                          "text-sm font-bold group-hover:text-primary transition-colors leading-tight",
                          hub.status === 'inactive' ? "text-outline dark:text-slate-500 italic" : "text-on-surface dark:text-white"
                        )}>
                          {hub.name}
                        </p>
                        <p className="text-[10px] text-outline dark:text-slate-500 truncate">
                          <span className={cn("font-mono", hub.status === 'inactive' && "line-through")}>{getHubUrl(hub.code)}</span>
                          <span className="mx-1.5 text-outline-variant dark:text-slate-600">·</span>
                          Cập nhật {hub.lastUpdate}
                        </p>
                      </div>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className="text-sm font-bold text-on-surface dark:text-slate-200">{hub.pages}</span>
                    <span className="text-xs text-outline dark:text-slate-500 ml-1">trang</span>
                  </td>
                  <td className="px-5 py-4">
                    <div className="flex items-center gap-1.5">
                      <Users size={13} className="text-outline dark:text-slate-500" />
                      <span className="text-sm font-semibold text-on-surface dark:text-slate-200">{hub.users}</span>
                    </div>
                  </td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-bold border",
                      hub.status === 'active'
                        ? "bg-emerald-50 dark:bg-emerald-900/20 text-emerald-700 dark:text-emerald-400 border-emerald-200 dark:border-emerald-800/50"
                        : "bg-surface-container-low dark:bg-slate-800 text-on-surface-variant dark:text-slate-400 border-outline-variant dark:border-slate-700"
                    )}>
                      <span className={cn("w-1.5 h-1.5 rounded-full", hub.status === 'active' ? "bg-emerald-500" : "bg-outline")} />
                      {hub.status === 'active' ? 'Hoạt động' : 'Vô hiệu'}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    {hub.pendingSync > 0 ? (
                      <Link
                        to="/sync"
                        className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:underline"
                      >
                        <RefreshCw size={13} />
                        {hub.pendingSync} chờ
                      </Link>
                    ) : (
                      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-outline dark:text-slate-500">
                        <CheckCircle2 size={13} />
                        0 chờ
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Sync chờ duyệt — mẫu giao-dien-mau dashboard §"Sync chờ duyệt" (file rows) */}
      <div className="m3-card flex flex-col">
        <div className="p-5 border-b border-outline-variant dark:border-slate-700 flex justify-between items-center">
          <div className="flex items-center gap-2">
            <RefreshCw size={18} className="text-primary" />
            <h2 className="font-bold text-body-lg text-on-surface dark:text-white">Sync chờ duyệt</h2>
            {stats.pendingBatches > 0 && (
              <span className="ml-1 bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full uppercase tracking-wide">
                {stats.pendingBatches} yêu cầu
              </span>
            )}
          </div>
          <Link to="/sync" className="text-primary text-xs font-bold hover:underline">
            Xem tất cả
          </Link>
        </div>
        <div className="p-4 space-y-3">
          {pendingBatchesLoading ? (
            <div className="flex items-center justify-center gap-2 text-outline dark:text-slate-500 py-8">
              <Loader2 size={18} className="animate-spin" />
              <span className="text-sm">Đang tải hàng đợi...</span>
            </div>
          ) : pendingBatches.length === 0 ? (
            <div className="flex flex-col items-center justify-center text-outline dark:text-slate-500 py-10 space-y-2">
              <CheckCircle2 size={32} className="opacity-30 text-emerald-500" />
              <p className="text-sm font-medium">Tất cả đã được duyệt</p>
            </div>
          ) : (
            pendingBatches.map((batch) => {
              const ext = Object.keys(batch.files_summary || {})[0]?.toUpperCase() || 'FILE';
              const config = FILE_TYPE_CONFIG[ext.toLowerCase() as FileType];
              const Icon = config?.icon || FileText;
              const iconColor = config?.color.split(' ')[0] || 'text-primary';
              const title = batch.pages?.[0]?.title || `Batch ${batch.id.slice(0, 8)} (${batch.page_count} tệp)`;
              return (
                <div
                  key={batch.id}
                  className="flex items-center justify-between p-4 bg-surface-container-low/50 dark:bg-slate-800/30 rounded-xl border border-slate-200/40 dark:border-slate-700/40 hover:border-primary/30 transition-all group"
                >
                  <div className="flex items-center gap-4 min-w-0 flex-1">
                    <div className="w-10 h-10 bg-white dark:bg-slate-900 rounded-lg border border-slate-200 dark:border-slate-700 flex flex-col items-center justify-center shadow-sm shrink-0">
                      <span className="text-[8px] font-bold text-outline dark:text-slate-500 leading-none">{ext}</span>
                      <Icon size={16} className={cn("mt-0.5", iconColor)} />
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-on-surface dark:text-white truncate group-hover:text-primary transition-colors">
                        {title}
                      </p>
                      <p className="text-[11px] text-on-surface-variant dark:text-slate-400 truncate">
                        Nguồn: {batch.hub_name} · {formatFileSize(batch.total_size)} · {timeAgo(batch.submitted_at)}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-3">
                    <Link
                      to="/sync"
                      className="px-3 py-1.5 bg-primary text-white rounded-lg text-xs font-bold hover:brightness-110 transition-all"
                    >
                      Duyệt nạp
                    </Link>
                    <Link
                      to="/sync"
                      className="p-1.5 text-outline dark:text-slate-500 hover:text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
                      title="Xem chi tiết"
                    >
                      <Trash2 size={16} />
                    </Link>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      </div>{/* /center column */}

      {/* Right column: Activity Feed (col-span-4) */}
      <div className="lg:col-span-4">
        {/* Hoạt động gần đây — mẫu giao-dien-mau dashboard §"Activity Feed" timeline */}
        <div className="m3-card flex flex-col h-full">
          <div className="p-5 border-b border-outline-variant dark:border-slate-700 flex justify-between items-center">
            <h2 className="font-bold text-body-lg text-on-surface dark:text-white">Hoạt động gần đây</h2>
            <button className="p-1 text-slate-400 hover:bg-surface-container-low dark:hover:bg-slate-700 rounded-lg transition-colors" title="Tuỳ chọn">
              <MoreVertical size={18} />
            </button>
          </div>
          <div className="p-5 flex-1 flex flex-col">
            {logsLoading ? (
              <div className="flex items-center justify-center gap-2 text-outline dark:text-slate-500 py-12">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">Đang tải...</span>
              </div>
            ) : recentLogs.length === 0 ? (
              <div className="flex flex-col items-center justify-center text-outline dark:text-slate-500 py-12">
                <Activity size={32} className="opacity-20 mb-2" />
                <p className="text-sm">Chưa có hoạt động nào</p>
              </div>
            ) : (
              <div className="relative space-y-5 before:absolute before:left-[17px] before:top-3 before:bottom-3 before:w-px before:bg-slate-200 dark:before:bg-slate-700">
                {recentLogs.map((log) => (
                  <div key={log.id} className="relative flex gap-4">
                    <div className={cn(
                      "relative z-10 w-9 h-9 rounded-full flex items-center justify-center border-4 border-white dark:border-slate-900 shadow-sm shrink-0",
                      log.isAI
                        ? "bg-fuchsia-100 dark:bg-fuchsia-900/30 text-fuchsia-600 dark:text-fuchsia-400"
                        : "bg-primary/10 dark:bg-primary/20 text-primary"
                    )}>
                      {log.isAI ? <Activity size={14} /> : <User size={14} />}
                    </div>
                    <div className="flex-1 min-w-0 pt-1">
                      <p className="text-sm text-on-surface dark:text-slate-200 leading-relaxed">
                        <span className={cn("font-bold", log.isAI ? "text-fuchsia-600 dark:text-fuchsia-400" : "text-on-surface dark:text-white")}>
                          {log.user}
                        </span>
                        {' '}{getActionLabel(log.action)}
                        {log.target !== '—' && (
                          <> : <span className="font-semibold text-primary">{log.target}</span></>
                        )}
                      </p>
                      <div className="flex items-center gap-2 mt-0.5">
                        <span className="text-[11px] text-outline dark:text-slate-500">{log.timestamp}</span>
                        <span className="text-[11px] text-outline-variant dark:text-slate-600">·</span>
                        <span className="text-[11px] text-outline dark:text-slate-500">{log.hub}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* Mẫu — "Xem nhật ký đầy đủ" button bottom */}
            {!logsLoading && recentLogs.length > 0 && (
              <Link
                to="/logs"
                className="w-full mt-8 py-2.5 bg-surface-container-low dark:bg-slate-800 text-on-surface dark:text-slate-200 rounded-lg text-xs font-bold hover:bg-primary/10 dark:hover:bg-primary/20 hover:text-primary transition-colors text-center inline-flex items-center justify-center gap-1.5"
              >
                Xem nhật ký đầy đủ
                <ArrowRight size={13} />
              </Link>
            )}
          </div>
        </div>
      </div>{/* /right column */}
      </div>{/* /grid 12-col */}
    </div>
  );
};

export default Dashboard;
