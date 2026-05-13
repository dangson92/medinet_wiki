import React, { useState, useEffect, useCallback } from 'react';
import { api, type APIKeyAPI, type APIKeyWithPlaintextAPI, type HubAPI } from '../services/api';
import type { APIKey } from '../types';
import { cn } from '../lib/utils';
import { Key, Plus, Copy, Check, Trash2, AlertCircle, X, Cpu, Search, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';

/* ── Helpers ── */
function formatBytes(bytes: number): string {
  if (bytes === 0) return '0 KB';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const val = bytes / Math.pow(1024, i);
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`;
}

function relativeTime(iso?: string): string {
  if (!iso) return '—';
  const now = new Date();
  const date = new Date(iso);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays > 0) return `${diffDays} ngày trước`;
  if (diffHours > 0) return `${diffHours} giờ trước`;
  if (diffMins > 0) return `${diffMins} phút trước`;
  return 'Vừa xong';
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('vi-VN', { day: '2-digit', month: '2-digit', year: 'numeric' });
}

function mapAPIKeyToFE(k: APIKeyAPI, hubs: HubAPI[]): APIKey {
  const hubMap = new Map(hubs.map(h => [h.id, h.name]));
  const allowedHubs = (!k.allowed_hub_ids || k.allowed_hub_ids.length === 0)
    ? ['Tất cả Hub']
    : k.allowed_hub_ids.map(id => hubMap.get(id) || id);

  return {
    id: k.id,
    name: k.name,
    permissions: k.permissions,
    allowedHubs,
    allowedRAGConfigs: k.allowed_rag_configs || [],
    createdAt: formatDate(k.created_at),
    lastUsed: relativeTime(k.last_used_at),
    requests7d: k.requests_7d,
    requestsToday: k.requests_today,
    bandwidthUsed: formatBytes(k.bandwidth_used),
    rateLimit: k.rate_limit,
    status: k.status as 'active' | 'revoked',
  };
}

/* ── RAG configs (static for now, same as before) ── */
const RAG_CONFIGS = [
  { id: 'rag-1', name: 'Default (Gemini 2.0)' },
  { id: 'rag-2', name: 'High Precision (Text-004)' },
  { id: 'rag-3', name: 'Fast Retrieval (ChromaDB)' },
];

const APIKeyManagement = () => {
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isKeyModalOpen, setIsKeyModalOpen] = useState(false);
  const [isRevokeDialogOpen, setIsRevokeDialogOpen] = useState(false);
  const [selectedKey, setSelectedKey] = useState<any>(null);
  const [newKey, setNewKey] = useState('');
  const [copied, setCopied] = useState(false);
  const [ragFilter, setRagFilter] = useState('all');

  // API state
  const [apiKeys, setApiKeys] = useState<APIKey[]>([]);
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [revoking, setRevoking] = useState(false);

  // Form state for create modal
  const [formName, setFormName] = useState('');
  const [formPerms, setFormPerms] = useState<string[]>(['Read']);
  const [formAllHubs, setFormAllHubs] = useState(true);
  const [formHubIds, setFormHubIds] = useState<string[]>([]);
  const [formRateLimit, setFormRateLimit] = useState(100);
  const [formRagConfigs, setFormRagConfigs] = useState<string[]>([]);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [keysRes, hubsRes] = await Promise.all([
        api.getAPIKeys(),
        api.getHubs(),
      ]);
      const hubList = hubsRes.success && hubsRes.data ? hubsRes.data : [];
      setHubs(hubList);
      if (keysRes.success && keysRes.data) {
        setApiKeys(keysRes.data.map(k => mapAPIKeyToFE(k, hubList)));
      }
    } catch (err) {
      console.error('Failed to fetch API keys:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const resetForm = () => {
    setFormName('');
    setFormPerms(['Read']);
    setFormAllHubs(true);
    setFormHubIds([]);
    setFormRateLimit(100);
    setFormRagConfigs([]);
  };

  const handleCreateKey = async () => {
    setCreating(true);
    try {
      const res = await api.createAPIKey({
        name: formName,
        permissions: formPerms,
        allowed_hub_ids: formAllHubs ? undefined : formHubIds,
        rate_limit: formRateLimit,
      });
      if (res.success && res.data) {
        const data = res.data as APIKeyWithPlaintextAPI;
        setNewKey(data.plain_key);
        setIsAddModalOpen(false);
        setIsKeyModalOpen(true);
        resetForm();
        // Refetch list
        const [keysRes] = await Promise.all([api.getAPIKeys()]);
        if (keysRes.success && keysRes.data) {
          setApiKeys(keysRes.data.map(k => mapAPIKeyToFE(k, hubs)));
        }
      }
    } catch (err) {
      console.error('Failed to create API key:', err);
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async () => {
    if (!selectedKey) return;
    setRevoking(true);
    try {
      const res = await api.revokeAPIKey(selectedKey.id);
      if (res.success) {
        setIsRevokeDialogOpen(false);
        setSelectedKey(null);
        await fetchData();
      }
    } catch (err) {
      console.error('Failed to revoke API key:', err);
    } finally {
      setRevoking(false);
    }
  };

  const togglePerm = (perm: string) => {
    setFormPerms(prev => prev.includes(perm) ? prev.filter(p => p !== perm) : [...prev, perm]);
  };

  const toggleHub = (hubId: string) => {
    setFormHubIds(prev => prev.includes(hubId) ? prev.filter(id => id !== hubId) : [...prev, hubId]);
  };

  const toggleRag = (name: string) => {
    setFormRagConfigs(prev => prev.includes(name) ? prev.filter(r => r !== name) : [...prev, name]);
  };

  const filteredKeys = apiKeys.filter(key => {
    if (ragFilter === 'all') return true;
    return key.allowedRAGConfigs?.includes(ragFilter);
  });

  const handleCopy = () => {
    navigator.clipboard.writeText(newKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Quản lý API Key</h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Quản lý API key cho AI Agent truy cập Wiki qua MCP protocol</p>
        </div>
        <button
          onClick={() => { resetForm(); setIsAddModalOpen(true); }}
          className="btn-primary w-full sm:w-auto"
        >
          <Plus size={18} /> Tạo API Key Mới
        </button>
      </div>

      <div className="glass-card p-4 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex items-center gap-2 text-sm font-medium text-slate-600 dark:text-slate-300 shrink-0">
          <Cpu size={16} className="text-slate-400 dark:text-slate-500" />
          Lọc theo RAG:
        </div>
        <div className="flex items-center gap-3 flex-1">
          <select
            value={ragFilter}
            onChange={(e) => setRagFilter(e.target.value)}
            className="input-field flex-1 sm:min-w-[200px]"
          >
            <option value="all">Tất cả cấu hình</option>
            {RAG_CONFIGS.map(rag => (
              <option key={rag.id} value={rag.name}>{rag.name}</option>
            ))}
          </select>
          {ragFilter !== 'all' && (
            <button
              onClick={() => setRagFilter('all')}
              className="text-xs text-accent font-bold hover:underline whitespace-nowrap"
            >
              Xóa lọc
            </button>
          )}
        </div>
      </div>

      <div className="glass-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[900px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tên key</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Quyền</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Hub được phép</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">RAG Access</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-center">Usage (Today)</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Ngày tạo</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Dùng cuối</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-center">Requests 7d</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {loading ? (
                <tr>
                  <td colSpan={10} className="px-5 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-400 dark:text-slate-500">
                      <Loader2 size={18} className="animate-spin" />
                      <span className="text-sm">Đang tải API Keys...</span>
                    </div>
                  </td>
                </tr>
              ) : filteredKeys.length > 0 ? (
                filteredKeys.map((key) => (
                  <tr key={key.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700 transition-colors group">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <Key size={14} className="text-slate-400 dark:text-slate-500" />
                        <span className="font-semibold text-sm text-slate-900 dark:text-white">{key.name}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex gap-1">
                        {key.permissions.map(p => (
                          <span key={p} className="text-[10px] font-medium px-1.5 py-0.5 rounded bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
                            {p}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-600 dark:text-slate-300">{key.allowedHubs.join(', ')}</td>
                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1">
                        {key.allowedRAGConfigs?.length ? key.allowedRAGConfigs.map(rag => (
                          <span key={rag} className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-accent/10 text-accent border border-accent/20">
                            {rag}
                          </span>
                        )) : <span className="text-xs text-slate-400 dark:text-slate-500">—</span>}
                      </div>
                    </td>
                    <td className="px-5 py-4">
                      <div className="flex flex-col items-center gap-1">
                        <span className="text-xs font-bold text-slate-900 dark:text-white">{key.requestsToday} reqs</span>
                        <span className="text-[10px] text-slate-400 dark:text-slate-500">{key.bandwidthUsed}</span>
                      </div>
                    </td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{key.createdAt}</td>
                    <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{key.lastUsed}</td>
                    <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300 text-center font-mono">{key.requests7d.toLocaleString()}</td>
                    <td className="px-5 py-4">
                      <span className={cn(
                        "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                        key.status === 'active' ? "bg-success/10 text-success" : "bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500"
                      )}>
                        {key.status === 'active' ? 'Đang hoạt động' : 'Đã thu hồi'}
                      </span>
                    </td>
                    <td className="px-5 py-4 text-right">
                      {key.status === 'active' && (
                        <button
                          onClick={() => { setSelectedKey(key); setIsRevokeDialogOpen(true); }}
                          className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500 hover:text-danger transition-colors"
                          title="Thu hồi"
                        >
                          <Trash2 size={16} />
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={10} className="px-5 py-6 sm:py-12 text-center">
                    <div className="flex flex-col items-center gap-2 text-slate-400 dark:text-slate-500">
                      <Search size={32} />
                      <p className="text-sm">Không tìm thấy API Key nào khớp với bộ lọc.</p>
                      <button
                        onClick={() => setRagFilter('all')}
                        className="text-accent text-xs font-bold hover:underline mt-2"
                      >
                        Xóa bộ lọc
                      </button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      <AnimatePresence>
        {isAddModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsAddModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-lg glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                <h3 className="text-lg font-semibold">Tạo API Key Mới</h3>
                <button onClick={() => setIsAddModalOpen(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 space-y-5 max-h-[70vh] overflow-y-auto">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên key</label>
                  <input
                    type="text"
                    placeholder="Ví dụ: Claude Desktop — Team AI"
                    className="input-field w-full"
                    value={formName}
                    onChange={(e) => setFormName(e.target.value)}
                  />
                </div>

                <div className="grid grid-cols-2 gap-6">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Phạm vi quyền</label>
                    <div className="space-y-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input type="checkbox" checked disabled className="text-accent rounded focus:ring-accent" />
                        <span className="text-sm text-slate-700 dark:text-slate-200">Read (luôn bật)</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          className="text-accent rounded focus:ring-accent"
                          checked={formPerms.includes('Write')}
                          onChange={() => togglePerm('Write')}
                        />
                        <span className="text-sm text-slate-700 dark:text-slate-200">Write</span>
                      </label>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          className="text-accent rounded focus:ring-accent"
                          checked={formPerms.includes('Cross-hub Search')}
                          onChange={() => togglePerm('Cross-hub Search')}
                        />
                        <span className="text-sm text-slate-700 dark:text-slate-200">Cross-hub Search</span>
                      </label>
                    </div>
                  </div>

                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Hub được phép</label>
                    <div className="space-y-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700 max-h-[120px] overflow-y-auto">
                      <label className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={formAllHubs}
                          onChange={() => { setFormAllHubs(!formAllHubs); if (!formAllHubs) setFormHubIds([]); }}
                          className="text-accent rounded focus:ring-accent"
                        />
                        <span className="text-sm text-slate-700 dark:text-slate-200">Tất cả Hub</span>
                      </label>
                      {hubs.map(h => (
                        <label key={h.id} className="flex items-center gap-2 cursor-pointer">
                          <input
                            type="checkbox"
                            className="text-accent rounded focus:ring-accent"
                            checked={formAllHubs || formHubIds.includes(h.id)}
                            disabled={formAllHubs}
                            onChange={() => toggleHub(h.id)}
                          />
                          <span className="text-sm text-slate-700 dark:text-slate-200">{h.name}</span>
                        </label>
                      ))}
                    </div>
                  </div>
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center gap-2 mb-1">
                    <Cpu size={14} className="text-slate-400 dark:text-slate-500" />
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Cấu hình RAG được phép</label>
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700">
                    {RAG_CONFIGS.map(rag => (
                      <label key={rag.id} className="flex items-center gap-2 cursor-pointer hover:bg-white/50 dark:hover:bg-slate-700 p-1 rounded transition-colors">
                        <input
                          type="checkbox"
                          className="text-accent rounded focus:ring-accent"
                          checked={formRagConfigs.includes(rag.name)}
                          onChange={() => toggleRag(rag.name)}
                        />
                        <span className="text-xs text-slate-700 dark:text-slate-200">{rag.name}</span>
                      </label>
                    ))}
                  </div>
                  <p className="text-[10px] text-slate-400 dark:text-slate-500 italic">Key này sẽ chỉ có quyền truy cập vào các model RAG được chọn ở trên.</p>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Rate limit</label>
                    <div className="relative">
                      <input
                        type="number"
                        value={formRateLimit}
                        onChange={(e) => setFormRateLimit(Number(e.target.value))}
                        className="input-field w-full pr-12"
                      />
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 text-[10px] font-bold text-slate-400 dark:text-slate-500">/phút</span>
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Ngày hết hạn</label>
                    <input type="text" placeholder="DD/MM/YYYY" className="input-field w-full" />
                  </div>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsAddModalOpen(false)} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleCreateKey}
                  className="btn-primary"
                  disabled={creating || !formName.trim()}
                >
                  {creating ? <><Loader2 size={16} className="animate-spin" /> Đang tạo...</> : 'Tạo Key'}
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isKeyModalOpen && (
          <div className="fixed inset-0 z-[60] flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/60 dark:bg-black/60"
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-lg glass-card shadow-lg p-8"
            >
              <div className="text-center mb-6">
                <div className="w-16 h-16 bg-success/10 text-success rounded-full flex items-center justify-center mx-auto mb-4">
                  <Key size={32} />
                </div>
                <h3 className="text-xl font-bold text-slate-900 dark:text-white">Key đã được tạo thành công!</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  Hãy sao chép và lưu key này ngay bây giờ. Vì lý do bảo mật, <span className="text-danger font-bold">chúng tôi sẽ không hiển thị lại key này lần nữa.</span>
                </p>
              </div>

              <div className="bg-slate-900 rounded-2xl p-6 relative group">
                <p className="text-xs font-mono text-slate-300 break-all leading-relaxed pr-8">
                  {newKey}
                </p>
                <button
                  onClick={handleCopy}
                  className="absolute top-4 right-4 p-2 rounded-lg bg-white/10 text-white hover:bg-white/20 transition-all"
                >
                  {copied ? <Check size={16} className="text-success" /> : <Copy size={16} />}
                </button>
              </div>

              <button
                onClick={() => setIsKeyModalOpen(false)}
                className="btn-primary w-full mt-8"
              >
                {copied ? "Đã sao chép, Đóng" : "Sao chép & Đóng"}
              </button>
            </motion.div>
          </div>
        )}

        {isRevokeDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsRevokeDialogOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-sm glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6">
                <div className="w-12 h-12 bg-danger/10 text-danger rounded-full flex items-center justify-center mb-4">
                  <AlertCircle size={24} />
                </div>
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Thu hồi API Key?</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  Thu hồi key <span className="font-bold text-slate-700 dark:text-slate-200">'{selectedKey?.name}'</span>? Key sẽ ngừng hoạt động ngay lập tức và không thể khôi phục.
                </p>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsRevokeDialogOpen(false)} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleRevoke}
                  className="btn-primary !bg-danger !shadow-none hover:!bg-danger/90"
                  disabled={revoking}
                >
                  {revoking ? <><Loader2 size={16} className="animate-spin" /> Đang thu hồi...</> : 'Thu hồi'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default APIKeyManagement;
