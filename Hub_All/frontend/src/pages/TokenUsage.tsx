import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  api, HubAPI, TokenUsageAPI, TokenUsageStatsAPI, TokenUsageRealtimeAPI,
} from '../services/api';
import { cn } from '../lib/utils';
import { Calendar, Loader2, Activity, Zap, AlertTriangle, Clock, RefreshCw, Radio } from 'lucide-react';
import Pagination from '../components/Pagination';

// Range presets → drive the auto-granularity on the backend.
// Labels are for the UI; `days` is what we send as date_from delta.
type RangeKey = '1h' | '24h' | '7d' | '30d' | '90d' | 'custom';
const RANGE_PRESETS: { key: RangeKey; label: string; days: number | null }[] = [
  { key: '1h',  label: '1 giờ',   days: 1 / 24 },
  { key: '24h', label: '24 giờ',  days: 1 },
  { key: '7d',  label: '7 ngày',  days: 7 },
  { key: '30d', label: '30 ngày', days: 30 },
  { key: '90d', label: '90 ngày', days: 90 },
  { key: 'custom', label: 'Tuỳ chỉnh', days: null },
];

const DETAIL_MAX_DAYS = 7; // must match backend repository.MaxDetailRangeDays

const formatNum = (n: number) => n.toLocaleString('vi-VN');
const fmtDate = (s: string) => new Date(s).toLocaleString('vi-VN');

const StatCard = ({
  icon: Icon, label, value, accent,
}: { icon: React.ElementType; label: string; value: string; accent: string }) => (
  <div className="m3-card p-4 flex items-center gap-3">
    <div className={cn('w-10 h-10 rounded-lg flex items-center justify-center', accent)}>
      <Icon size={18} />
    </div>
    <div className="min-w-0">
      <p className="text-[11px] text-on-surface-variant truncate">{label}</p>
      <p className="text-lg font-bold text-on-surface dark:text-white">{value}</p>
    </div>
  </div>
);

const GroupBar = ({
  groups, title,
}: { groups: { key: string; calls: number; total_tokens: number }[]; title: string }) => {
  const max = Math.max(1, ...groups.map(g => g.total_tokens));
  return (
    <div className="m3-card p-4">
      <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3">{title}</h3>
      {groups.length === 0 && <p className="text-xs text-outline">Chưa có dữ liệu</p>}
      <div className="space-y-2">
        {groups.map(g => (
          <div key={g.key}>
            <div className="flex justify-between text-xs mb-1">
              <span className="font-mono text-slate-700 dark:text-slate-300 truncate">{g.key}</span>
              <span className="text-on-surface-variant">
                {formatNum(g.total_tokens)} tok · {formatNum(g.calls)} calls
              </span>
            </div>
            <div className="h-1.5 bg-slate-100 dark:bg-slate-800 rounded-full overflow-hidden">
              <div
                className="h-full bg-primary rounded-full"
                style={{ width: `${Math.max(2, (g.total_tokens / max) * 100)}%` }}
              />
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

const TokenUsage = () => {
  const [hubs, setHubs] = useState<HubAPI[]>([]);

  // Filters
  const [rangeKey, setRangeKey] = useState<RangeKey>('24h');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [provider, setProvider] = useState('');
  const [operation, setOperation] = useState('');
  const [hubId, setHubId] = useState('');
  const [status, setStatus] = useState('');

  // Realtime toggle
  const [realtimeOn, setRealtimeOn] = useState(false);

  // Data
  const [stats, setStats] = useState<TokenUsageStatsAPI | null>(null);
  const [realtime, setRealtime] = useState<TokenUsageRealtimeAPI | null>(null);
  const [logs, setLogs] = useState<TokenUsageAPI[]>([]);
  const [detailErr, setDetailErr] = useState<string | null>(null);

  // UI state
  const [statsLoading, setStatsLoading] = useState(false);
  const [logsLoading, setLogsLoading] = useState(false);
  const [page, setPage] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const itemsPerPage = 20;

  const realtimeTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const statsTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ─── Compute date_from / date_to from preset ───
  const effectiveRange = useMemo(() => {
    const preset = RANGE_PRESETS.find(p => p.key === rangeKey);
    if (!preset) return { date_from: dateFrom, date_to: dateTo };
    if (preset.days === null) return { date_from: dateFrom, date_to: dateTo };
    const now = new Date();
    const from = new Date(now.getTime() - preset.days * 24 * 60 * 60 * 1000);
    return {
      date_from: from.toISOString(),
      date_to: now.toISOString(),
    };
  }, [rangeKey, dateFrom, dateTo]);

  const detailTooWide = useMemo(() => {
    const preset = RANGE_PRESETS.find(p => p.key === rangeKey);
    if (!preset || preset.days === null) {
      // Custom — validate user input.
      if (!dateFrom || !dateTo) return false;
      const days = (new Date(dateTo).getTime() - new Date(dateFrom).getTime()) / (24 * 3600 * 1000);
      return days > DETAIL_MAX_DAYS;
    }
    return preset.days > DETAIL_MAX_DAYS;
  }, [rangeKey, dateFrom, dateTo]);

  const filters = useMemo(() => ({
    ...effectiveRange,
    provider: provider || undefined,
    operation: operation || undefined,
    hub_id: hubId || undefined,
    status: status || undefined,
  }), [effectiveRange, provider, operation, hubId, status]);

  useEffect(() => {
    api.getHubs().then(r => { if (r.success && r.data) setHubs(r.data); });
  }, []);

  // ─── Fetch stats (rollup-backed, cached by backend 5s) ───
  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await api.getTokenUsageStats(filters);
      if (res.success && res.data) setStats(res.data);
    } finally {
      setStatsLoading(false);
    }
  }, [filters]);

  // ─── Fetch detail table — only if range ≤ 7 days ───
  const fetchLogs = useCallback(async () => {
    if (detailTooWide) {
      setLogs([]);
      setTotalItems(0);
      setTotalPages(1);
      setDetailErr(`Dải thời gian vượt ${DETAIL_MAX_DAYS} ngày — chọn dải ngắn hơn để xem chi tiết.`);
      return;
    }
    setLogsLoading(true);
    setDetailErr(null);
    try {
      const res = await api.getTokenUsage({ ...filters, page, per_page: itemsPerPage });
      if (res.success && res.data) {
        setLogs(res.data);
        if (res.meta) {
          setTotalItems(res.meta.total);
          setTotalPages(res.meta.total_pages);
        }
      } else if (res.error) {
        setDetailErr(res.error.message);
        setLogs([]);
      }
    } finally {
      setLogsLoading(false);
    }
  }, [filters, page, detailTooWide]);

  // ─── Realtime polling (last 60 min from Redis) ───
  const fetchRealtime = useCallback(async () => {
    const res = await api.getTokenUsageRealtime();
    if (res.success && res.data) setRealtime(res.data);
  }, []);

  useEffect(() => { fetchStats(); }, [fetchStats]);
  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  // Auto-refresh stats every 10s (backend serves from 5s-TTL cache, so
  // this keeps the dashboard fresh without hammering Postgres).
  useEffect(() => {
    statsTimerRef.current = setInterval(fetchStats, 10_000);
    return () => { if (statsTimerRef.current) clearInterval(statsTimerRef.current); };
  }, [fetchStats]);

  // Realtime poll every 2s when the panel is open.
  useEffect(() => {
    if (!realtimeOn) {
      if (realtimeTimerRef.current) clearInterval(realtimeTimerRef.current);
      return;
    }
    fetchRealtime();
    realtimeTimerRef.current = setInterval(fetchRealtime, 2_000);
    return () => { if (realtimeTimerRef.current) clearInterval(realtimeTimerRef.current); };
  }, [realtimeOn, fetchRealtime]);

  const handleReset = () => {
    setRangeKey('24h');
    setDateFrom(''); setDateTo('');
    setProvider(''); setOperation(''); setHubId(''); setStatus('');
    setPage(1);
  };

  const refreshAll = () => {
    fetchStats();
    fetchLogs();
    if (realtimeOn) fetchRealtime();
  };

  // ─── Render ───
  return (
    <div className="space-y-6">
      {/* Header — đồng bộ M3 với HubRegistry / UserManagement / Settings */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-end gap-4">
        <div>
          <h1 className="font-display text-headline-xl text-on-surface dark:text-white">
            Token & API Usage
          </h1>
          <p className="text-body-md text-on-surface-variant mt-1">
            Theo dõi chi phí token Gemini / OpenAI — số liệu tổng hợp từ rollup, realtime từ Redis.
          </p>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => setRealtimeOn(v => !v)}
            className={cn(
              'inline-flex items-center gap-2 px-4 py-2 border rounded-lg text-body-sm font-semibold transition-colors',
              realtimeOn
                ? 'bg-primary/10 border-primary/40 text-primary'
                : 'bg-white border-outline-variant text-on-surface hover:bg-surface-container-low dark:bg-slate-800 dark:border-slate-700 dark:text-white'
            )}
          >
            <Radio size={16} className={cn(realtimeOn && 'animate-pulse')} />
            {realtimeOn ? 'Realtime ON' : 'Realtime'}
          </button>
          <button
            onClick={refreshAll}
            className="inline-flex items-center gap-2 px-4 py-2 bg-white border border-outline-variant rounded-lg text-body-sm font-semibold text-on-surface hover:bg-surface-container-low transition-colors dark:bg-slate-800 dark:border-slate-700 dark:text-white"
          >
            <RefreshCw size={16} /> Làm mới
          </button>
        </div>
      </div>

      {/* Range presets */}
      <div className="m3-card p-4 space-y-3">
        <div className="flex flex-wrap gap-2">
          {RANGE_PRESETS.map(p => (
            <button
              key={p.key}
              onClick={() => { setRangeKey(p.key); setPage(1); }}
              className={cn(
                'px-3 py-1.5 text-xs rounded-full border transition-all',
                rangeKey === p.key
                  ? 'bg-primary text-white border-primary'
                  : 'bg-white dark:bg-slate-800 border-outline-variant dark:border-slate-700 text-on-surface-variant dark:text-slate-300 hover:border-primary/40',
              )}
            >
              {p.label}
            </button>
          ))}
        </div>

        {rangeKey === 'custom' && (
          <div className="flex items-center gap-2">
            <div className="relative flex-1 lg:w-40">
              <Calendar size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline" />
              <input type="date" value={dateFrom}
                onChange={e => { setDateFrom(e.target.value); setPage(1); }}
                className="input-field w-full pl-8" />
            </div>
            <span className="text-slate-300 dark:text-slate-600 shrink-0">→</span>
            <div className="relative flex-1 lg:w-40">
              <input type="date" value={dateTo}
                onChange={e => { setDateTo(e.target.value); setPage(1); }}
                className="input-field w-full" />
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <select className="input-field w-full" value={provider} onChange={e => { setProvider(e.target.value); setPage(1); }}>
            <option value="">Tất cả nhà cung cấp</option>
            <option value="gemini">Gemini</option>
            <option value="openai">OpenAI</option>
          </select>
          <select className="input-field w-full" value={operation} onChange={e => { setOperation(e.target.value); setPage(1); }}>
            <option value="">Tất cả thao tác</option>
            <option value="chat">Chat (LLM)</option>
            <option value="embed">Embed</option>
          </select>
          <select className="input-field w-full" value={hubId} onChange={e => { setHubId(e.target.value); setPage(1); }}>
            <option value="">Tất cả Hub</option>
            {hubs.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
          </select>
          <select className="input-field w-full" value={status} onChange={e => { setStatus(e.target.value); setPage(1); }}>
            <option value="">Tất cả trạng thái</option>
            <option value="success">Success</option>
            <option value="error">Error</option>
          </select>
        </div>

        <div className="flex justify-end">
          <button onClick={handleReset} className="btn-ghost">Reset</button>
        </div>
      </div>

      {/* Realtime panel */}
      {realtimeOn && (
        <div className="m3-card p-4 border-2 border-primary/30">
          <div className="flex items-center gap-2 mb-3">
            <Radio size={14} className="text-primary animate-pulse" />
            <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface dark:text-white">
              Realtime — 60 phút gần nhất (Redis, cập nhật mỗi 2s)
            </h3>
          </div>
          {!realtime && <p className="text-xs text-outline">Đang tải…</p>}
          {realtime && (
            <>
              <div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-4">
                <div className="m3-card p-3">
                  <p className="text-[10px] text-on-surface-variant">Calls (1h)</p>
                  <p className="text-lg font-bold">{formatNum(realtime.totals.calls)}</p>
                </div>
                <div className="m3-card p-3">
                  <p className="text-[10px] text-on-surface-variant">Tokens (1h)</p>
                  <p className="text-lg font-bold">{formatNum(realtime.totals.total_tokens)}</p>
                </div>
                <div className="m3-card p-3">
                  <p className="text-[10px] text-on-surface-variant">Prompt</p>
                  <p className="text-lg font-bold">{formatNum(realtime.totals.prompt_tokens)}</p>
                </div>
                <div className="m3-card p-3">
                  <p className="text-[10px] text-on-surface-variant">Output</p>
                  <p className="text-lg font-bold">{formatNum(realtime.totals.output_tokens)}</p>
                </div>
                <div className="m3-card p-3">
                  <p className="text-[10px] text-on-surface-variant">Avg latency</p>
                  <p className="text-lg font-bold">{Math.round(realtime.totals.avg_latency_ms)} ms</p>
                </div>
              </div>
              <div className="flex items-end gap-0.5 h-24">
                {(() => {
                  const max = Math.max(1, ...realtime.points.map(p => p.total_tokens));
                  return realtime.points.map((p, i) => (
                    <div key={i} className="flex-1 flex flex-col items-center group relative">
                      <div
                        className={cn(
                          'w-full rounded-t transition-all',
                          p.errors > 0 ? 'bg-danger/70' : 'bg-primary/70 group-hover:bg-primary',
                        )}
                        style={{ height: `${Math.max(2, (p.total_tokens / max) * 100)}%` }}
                      />
                      <span className="absolute -top-7 opacity-0 group-hover:opacity-100 bg-inverse-surface text-inverse-on-surface text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap z-10">
                        {p.minute}: {formatNum(p.total_tokens)} tok · {formatNum(p.calls)} calls
                      </span>
                    </div>
                  ));
                })()}
              </div>
            </>
          )}
        </div>
      )}

      {/* Aggregate stats (rollup-backed) */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
        <StatCard icon={Zap} label="Tổng tokens" value={statsLoading ? '...' : formatNum(stats?.total_tokens ?? 0)} accent="bg-primary/10 text-primary" />
        <StatCard icon={Activity} label="Tổng lượt gọi" value={statsLoading ? '...' : formatNum(stats?.total_calls ?? 0)} accent="bg-tertiary/10 text-tertiary" />
        <StatCard icon={Zap} label="Prompt tokens" value={statsLoading ? '...' : formatNum(stats?.total_prompt_tokens ?? 0)} accent="bg-emerald-500/10 text-emerald-500" />
        <StatCard icon={Zap} label="Output tokens" value={statsLoading ? '...' : formatNum(stats?.total_output_tokens ?? 0)} accent="bg-sky-500/10 text-sky-500" />
        <StatCard icon={AlertTriangle} label="Lỗi" value={statsLoading ? '...' : formatNum(stats?.error_calls ?? 0)} accent="bg-danger/10 text-danger" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <GroupBar title="Theo nhà cung cấp" groups={stats?.by_provider ?? []} />
        <GroupBar title="Theo model" groups={stats?.by_model ?? []} />
        <GroupBar title="Theo thao tác" groups={stats?.by_operation ?? []} />
      </div>

      {/* Timeline — granularity auto-picked by backend based on range */}
      <div className="m3-card p-4">
        <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant mb-3 flex items-center gap-2">
          <Clock size={14} /> Tokens theo thời gian
        </h3>
        {(stats?.daily?.length ?? 0) === 0 ? (
          <p className="text-xs text-outline">Chưa có dữ liệu</p>
        ) : (
          <div className="flex items-end gap-1 h-32">
            {(() => {
              const max = Math.max(1, ...(stats?.daily ?? []).map(d => d.total_tokens));
              return (stats?.daily ?? []).map(d => (
                <div key={d.date} className="flex-1 flex flex-col items-center justify-end h-full group relative">
                  <div
                    className="w-full bg-primary/70 hover:bg-primary rounded-t transition-all"
                    style={{ height: `${Math.max(2, (d.total_tokens / max) * 100)}%` }}
                  />
                  <span className="absolute -top-7 opacity-0 group-hover:opacity-100 bg-inverse-surface text-inverse-on-surface text-[10px] px-1.5 py-0.5 rounded whitespace-nowrap z-10">
                    {d.date}: {formatNum(d.total_tokens)} tok
                  </span>
                </div>
              ));
            })()}
          </div>
        )}
      </div>

      {/* Detail table (raw) — only for ranges ≤ 7 days */}
      <div className="m3-card overflow-hidden">
        <div className="p-4 border-b border-slate-200/50 dark:border-slate-700/50 flex items-center justify-between">
          <h3 className="text-xs font-bold uppercase tracking-wider text-on-surface-variant">
            Chi tiết từng lời gọi (raw)
          </h3>
          <span className="text-[10px] text-outline">
            Giới hạn dải {DETAIL_MAX_DAYS} ngày để bảo vệ DB
          </span>
        </div>
        <div className="overflow-x-auto">
          {detailErr ? (
            <div className="flex items-center justify-center py-12 text-xs text-on-surface-variant">
              {detailErr}
            </div>
          ) : logsLoading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-primary" size={28} />
            </div>
          ) : (
            <table className="w-full text-left border-collapse min-w-[900px]">
              <thead className="bg-surface-container-low border-b border-outline-variant dark:bg-slate-900/50">
                <tr>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Thời gian</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Provider</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Model</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Op</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Module</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline text-right">Prompt</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline text-right">Output</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline text-right">Total</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline text-right">Lat (ms)</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">Trạng thái</th>
                  <th className="px-4 py-4 text-[11px] font-bold uppercase tracking-wider text-outline">User</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-outline-variant dark:divide-slate-700">
                {logs.length === 0 && (
                  <tr><td colSpan={11} className="text-center py-12 text-xs text-outline">
                    Chưa có lượt gọi nào trong dải đã chọn.
                  </td></tr>
                )}
                {logs.map(l => (
                  <tr key={l.id} className="hover:bg-surface-container-low/50 dark:hover:bg-slate-700 transition-colors">
                    <td className="px-4 py-3 text-body-sm text-on-surface-variant dark:text-slate-300 whitespace-nowrap">{fmtDate(l.timestamp)}</td>
                    <td className="px-4 py-3 text-body-sm">
                      <span className={cn(
                        'px-2 py-0.5 rounded text-[10px] font-semibold uppercase',
                        l.provider === 'gemini' ? 'bg-tertiary/10 text-tertiary' : 'bg-emerald-500/10 text-emerald-600',
                      )}>{l.provider}</span>
                    </td>
                    <td className="px-4 py-3 text-body-sm font-mono text-on-surface-variant dark:text-slate-300">{l.model}</td>
                    <td className="px-4 py-3 text-body-sm text-on-surface-variant dark:text-slate-300">{l.operation}</td>
                    <td className="px-4 py-3 text-body-sm text-on-surface-variant">{l.source_module || '—'}</td>
                    <td className="px-4 py-3 text-body-sm text-right font-mono text-on-surface-variant dark:text-slate-300">{formatNum(l.prompt_tokens)}</td>
                    <td className="px-4 py-3 text-body-sm text-right font-mono text-on-surface-variant dark:text-slate-300">{formatNum(l.output_tokens)}</td>
                    <td className="px-4 py-3 text-body-sm text-right font-mono font-semibold text-on-surface dark:text-white">{formatNum(l.total_tokens)}</td>
                    <td className="px-4 py-3 text-body-sm text-right font-mono text-on-surface-variant">{l.latency_ms}</td>
                    <td className="px-4 py-3 text-body-sm">
                      <span
                        className={cn(
                          'px-2 py-0.5 rounded text-[10px] font-semibold uppercase cursor-default',
                          l.status === 'success' ? 'bg-emerald-500/10 text-emerald-600' : 'bg-danger/10 text-danger',
                        )}
                        title={l.status === 'error' && l.error_message ? l.error_message : undefined}
                      >{l.status}</span>
                      {l.status === 'error' && l.error_message && (
                        <p className="mt-0.5 text-[10px] text-danger/80 max-w-[200px] truncate" title={l.error_message}>
                          {l.error_message}
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-body-sm text-on-surface-variant">{l.user_name || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        {!detailErr && (
          <Pagination
            currentPage={page}
            totalPages={totalPages}
            onPageChange={setPage}
            totalItems={totalItems}
            itemsPerPage={itemsPerPage}
          />
        )}
      </div>
    </div>
  );
};

export default TokenUsage;
