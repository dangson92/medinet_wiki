import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { api, HubAPI, AuditLogAPI } from '../services/api';
import { AuditLogEntry } from '../types';
import { cn } from '../lib/utils';
import { Search, Filter, Download, Calendar, User, Activity, ChevronDown, ChevronUp, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Pagination from '../components/Pagination';

const AuditLog = () => {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [isExporting, setIsExporting] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  // Data state
  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);

  // Filter state
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [actorType, setActorType] = useState('');
  const [actionFilter, setActionFilter] = useState('');
  const [hubFilter, setHubFilter] = useState('');

  // Applied filters (only sent to API when "Áp dụng" is clicked)
  const [appliedFilters, setAppliedFilters] = useState<{
    date_from?: string;
    date_to?: string;
    actor_type?: string;
    action?: string;
    hub_id?: string;
  }>({});

  // Fetch hubs on mount
  useEffect(() => {
    const fetchHubs = async () => {
      try {
        const res = await api.getHubs();
        if (res.success && res.data) {
          setHubs(res.data);
        }
      } catch (err) {
        console.error('Failed to fetch hubs:', err);
      }
    };
    fetchHubs();
  }, []);

  // Map API audit log to FE type
  const mapLog = useCallback((item: AuditLogAPI): AuditLogEntry => {
    return {
      id: item.id,
      timestamp: new Date(item.timestamp).toLocaleString('vi-VN'),
      user: item.user_name || 'Unknown',
      isAI: item.is_ai,
      action: item.action as AuditLogEntry['action'],
      target: item.target || '',
      hub: item.hub_name || '',
      ip: item.ip_address || '',
      userAgent: item.user_agent,
      requestId: item.request_id,
      durationMs: item.duration_ms,
      payload: item.payload,
    };
  }, []);

  // Fetch audit logs
  const fetchLogs = useCallback(async () => {
    setLoading(true);
    try {
      const params: any = {
        page: currentPage,
        per_page: itemsPerPage,
        ...appliedFilters,
      };

      const res = await api.getAuditLogs(params);
      if (res.success && res.data) {
        setLogs(res.data.map(mapLog));
        if (res.meta) {
          setTotalItems(res.meta.total);
          setTotalPages(res.meta.total_pages);
        } else {
          setTotalItems(res.data.length);
          setTotalPages(Math.ceil(res.data.length / itemsPerPage));
        }
      }
    } catch (err) {
      console.error('Failed to fetch audit logs:', err);
    } finally {
      setLoading(false);
    }
  }, [currentPage, appliedFilters, mapLog]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  const handleApplyFilters = () => {
    const filters: typeof appliedFilters = {};
    if (dateFrom) filters.date_from = dateFrom;
    if (dateTo) filters.date_to = dateTo;
    if (actorType) filters.actor_type = actorType;
    if (actionFilter) filters.action = actionFilter;
    if (hubFilter) filters.hub_id = hubFilter;
    setAppliedFilters(filters);
    setCurrentPage(1);
  };

  const handleResetFilters = () => {
    setDateFrom('');
    setDateTo('');
    setActorType('');
    setActionFilter('');
    setHubFilter('');
    setAppliedFilters({});
    setCurrentPage(1);
  };

  const handleExport = async () => {
    setIsExporting(true);
    try {
      const API_URL = import.meta.env.VITE_API_URL || `http://${window.location.hostname}:8180`;
      const token = localStorage.getItem('access_token');
      const params = new URLSearchParams();
      if (appliedFilters.date_from) params.set('date_from', appliedFilters.date_from);
      if (appliedFilters.date_to) params.set('date_to', appliedFilters.date_to);
      if (appliedFilters.action) params.set('action', appliedFilters.action);
      if (appliedFilters.hub_id) params.set('hub_id', appliedFilters.hub_id);
      const qs = params.toString();
      const res = await fetch(`${API_URL}/api/audit-logs/export${qs ? '?' + qs : ''}`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
        document.body.appendChild(a);
        a.click();
        a.remove();
        window.URL.revokeObjectURL(url);
      }
    } catch (err) {
      console.error('Export failed:', err);
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-h1 font-bold text-slate-900 dark:text-white tracking-tight">Audit Log</h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Lịch sử toàn bộ thao tác hệ thống</p>
        </div>
        <button
          onClick={handleExport}
          className="btn-secondary w-full sm:w-auto"
        >
          <Download size={18} /> Xuất CSV
        </button>
      </div>

      {/* Filter Bar */}
      <div className="glass-card p-4 flex flex-col lg:flex-row items-stretch lg:items-center gap-3">
        <div className="flex items-center gap-2">
          <div className="relative flex-1 lg:w-32">
            <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" />
            <input type="date" placeholder="Từ ngày" value={dateFrom} onChange={e => setDateFrom(e.target.value)} className="input-field w-full pl-8" />
          </div>
          <span className="text-slate-300 dark:text-slate-600 shrink-0">&rarr;</span>
          <div className="relative flex-1 lg:w-32">
            <input type="date" placeholder="Đến ngày" value={dateTo} onChange={e => setDateTo(e.target.value)} className="input-field w-full" />
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 flex-1">
          <select className="input-field w-full" value={actorType} onChange={e => setActorType(e.target.value)}>
            <option value="">Tất cả người thực hiện</option>
            <option value="human">Admin Hub Tổng</option>
            <option value="ai">AI Agent</option>
          </select>

          <select className="input-field w-full" value={actionFilter} onChange={e => setActionFilter(e.target.value)}>
            <option value="">Tất cả hành động</option>
            <option value="CREATE">CREATE</option>
            <option value="UPDATE">UPDATE</option>
            <option value="DELETE">DELETE</option>
            <option value="SYNC">SYNC</option>
            <option value="APPROVE_SYNC">APPROVE_SYNC</option>
            <option value="MCP_WRITE">MCP_WRITE</option>
          </select>

          <select className="input-field w-full" value={hubFilter} onChange={e => setHubFilter(e.target.value)}>
            <option value="">Tất cả Hub</option>
            {hubs.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
        </div>

        <div className="flex gap-2">
          <button onClick={handleApplyFilters} className="btn-primary flex-1 lg:flex-none">Áp dụng</button>
          <button onClick={handleResetFilters} className="btn-ghost flex-1 lg:flex-none">Reset</button>
        </div>
      </div>

      {/* Log Table */}
      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-accent" size={28} />
            </div>
          ) : (
          <table className="w-full text-left border-collapse min-w-[750px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="w-10"></th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Thời gian</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Người thực hiện</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Hành động</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trang bị ảnh hưởng</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Hub</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">IP</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {logs.map((log) => (
                <React.Fragment key={log.id}>
                  <tr
                    onClick={() => setExpandedId(expandedId === log.id ? null : log.id)}
                    className="hover:bg-slate-50/50 dark:hover:bg-slate-700 transition-colors cursor-pointer group"
                  >
                    <td className="pl-5 py-4">
                      {expandedId === log.id ? <ChevronUp size={14} className="text-slate-400 dark:text-slate-500" /> : <ChevronDown size={14} className="text-slate-400 dark:text-slate-500" />}
                    </td>
                    <td className="px-5 py-4 text-xs font-medium text-slate-600 dark:text-slate-300">{log.timestamp}</td>
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <div className={cn(
                          "w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold",
                          log.isAI ? "bg-brand-purple/10 text-brand-purple" : "bg-slate-100 dark:bg-slate-700 text-slate-500 dark:text-slate-400"
                        )}>
                          {log.isAI ? 'AI' : 'U'}
                        </div>
                        <span className={cn("text-sm font-semibold", log.isAI ? "text-brand-purple" : "text-slate-900 dark:text-white")}>
                          {log.isAI ? `[AI Agent] ${log.user}` : log.user}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 uppercase">
                        {log.action}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300 font-medium">{log.target}</td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{log.hub}</td>
                    <td className="px-5 py-4 text-xs font-mono text-slate-400 dark:text-slate-500">{log.ip}</td>
                  </tr>
                  <AnimatePresence>
                    {expandedId === log.id && (
                      <motion.tr
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        exit={{ opacity: 0, height: 0 }}
                        className="bg-slate-50/80 dark:bg-slate-800/50"
                      >
                        <td colSpan={7} className="px-4 sm:px-10 py-6">
                          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 sm:gap-8">
                            <div className="space-y-2">
                              <p className="text-xs text-slate-400 dark:text-slate-500">Request ID</p>
                              <p className="text-xs font-mono text-slate-600 dark:text-slate-300">{log.requestId || '—'}</p>
                            </div>
                            <div className="space-y-2">
                              <p className="text-xs text-slate-400 dark:text-slate-500">Duration</p>
                              <p className="text-xs font-mono text-slate-600 dark:text-slate-300">{log.durationMs != null ? `${log.durationMs}ms` : '—'}</p>
                            </div>
                            <div className="space-y-2">
                              <p className="text-xs text-slate-400 dark:text-slate-500">User Agent</p>
                              <p className="text-xs text-slate-600 dark:text-slate-300 truncate">{log.userAgent || '—'}</p>
                            </div>
                            {log.payload && (
                              <div className="col-span-full space-y-3">
                                <p className="text-xs text-slate-400 dark:text-slate-500">Payload</p>
                                <pre className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl p-4 font-mono text-xs overflow-x-auto whitespace-pre-wrap text-slate-600 dark:text-slate-300">
                                  {typeof log.payload === 'string' ? log.payload : JSON.stringify(log.payload as Record<string, unknown>, null, 2)}
                                </pre>
                              </div>
                            )}
                          </div>
                        </td>
                      </motion.tr>
                    )}
                  </AnimatePresence>
                </React.Fragment>
              ))}
            </tbody>
          </table>
          )}
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={totalItems}
          itemsPerPage={itemsPerPage}
        />
      </div>

      <AnimatePresence>
        {isExporting && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-sm glass-card shadow-lg p-8 text-center"
            >
              <div className="w-12 h-12 bg-accent/10 text-accent rounded-full flex items-center justify-center mx-auto mb-4">
                <Download size={24} />
              </div>
              <h3 className="text-lg font-semibold">Đang tải xuống...</h3>
              <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                Đang xuất file CSV cho {totalItems.toLocaleString()} records.
              </p>
              <div className="mt-4">
                <Loader2 className="animate-spin text-accent mx-auto" size={24} />
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default AuditLog;
