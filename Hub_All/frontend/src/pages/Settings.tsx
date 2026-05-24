import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  Cpu,
  Save,
  RefreshCw,
  Lock,
  Eye,
  Mail,
  Smartphone,
  Info,
  CheckCircle2,
  Database,
  Layers,
  ArrowRight,
  FileText,
  Check,
  AlertTriangle,
  Pencil,
  X,
  Sparkles,
  Plug,
} from 'lucide-react';
import { cn } from '../lib/utils';

// Phase 5 PROXY-02 fix: API fetch dùng absolute path /api/* — Caddy `/api/*` → central.
// rag-config / system-settings là central-only endpoint (strip ở hub con).
// MCP_URL CHỈ làm placeholder hint cho input field (line 648); admin custom sau qua tab MCP Connector.
const MCP_URL = import.meta.env.VITE_MCP_URL || `http://${window.location.hostname}:8190`;

// ─── Model metadata ───
interface ModelInfo {
  id: string;
  name: string;
  dimension: number;
  provider: 'gemini' | 'openai';
  cost: string;         // short label (e.g. "Miễn phí", "$0.13/1M")
  freeTier?: string;    // free quota description (e.g. "1,500 RPM / 100 RPD")
  paidPrice?: string;   // paid rate beyond free tier (e.g. "$0.15/1M tokens")
  notes?: string;       // extra context (e.g. "Preview — có thể đổi giá")
}

// Pricing tham khảo theo công bố của Google AI & OpenAI (cập nhật 2025-04)
const MODEL_CATALOG: ModelInfo[] = [
  {
    id: 'gemini-embedding-001',
    name: 'Gemini Embedding 001',
    dimension: 3072,
    provider: 'gemini',
    cost: 'Miễn phí → $0.15/1M',
    freeTier: '100 RPD free · 1,500 RPM',
    paidPrice: '$0.15 / 1M tokens',
    notes: 'Ổn định (GA), khuyến nghị cho production',
  },
  {
    id: 'gemini-embedding-2-preview',
    name: 'Gemini Embedding 2',
    dimension: 3072,
    provider: 'gemini',
    cost: 'Miễn phí (Preview)',
    freeTier: 'Preview — chưa tính phí',
    paidPrice: 'Sẽ áp giá khi GA',
    notes: 'Bản preview, chất lượng cao hơn 001 nhưng có thể đổi giá',
  },
  {
    id: 'text-embedding-3-small',
    name: 'OpenAI Small',
    dimension: 1536,
    provider: 'openai',
    cost: '$0.02/1M tokens',
    freeTier: 'Không có free tier',
    paidPrice: '$0.02 / 1M tokens',
    notes: 'Giá rẻ nhất, chất lượng đủ cho đa số use case',
  },
  {
    id: 'text-embedding-3-large',
    name: 'OpenAI Large',
    dimension: 3072,
    provider: 'openai',
    cost: '$0.13/1M tokens',
    freeTier: 'Không có free tier',
    paidPrice: '$0.13 / 1M tokens',
    notes: 'Chất lượng cao nhất, đắt gấp 6.5× Small',
  },
];

const SEPARATORS = ['# ## ### ####', '```', '---', '\\n\\n', '\\n', '. ? ! ;', ',', 'space', 'hard cut'];

// SectionHeader — numbered heading used to group RAG configuration cards.
type SectionHeaderProps = {
  number: string;
  title: string;
  badgeText?: string;
  description: string;
};
const SectionHeader = ({ number, title, badgeText, description }: SectionHeaderProps) => (
  <div className="mb-5">
    <div className="flex flex-wrap items-center gap-2">
      <h2 className="text-h3 font-bold text-slate-900 dark:text-white">
        {number}. {title}
      </h2>
      {badgeText && (
        <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded text-brand-indigo bg-brand-indigo/10">
          {badgeText}
        </span>
      )}
    </div>
    <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">{description}</p>
  </div>
);

export default function Settings() {
  const [activeTab, setActiveTab] = useState('general');
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // ─── General settings state ───
  const [systemName, setSystemName] = useState('Medinet Wiki');
  const [systemUrl, setSystemUrl] = useState('https://wiki.medinet.vn');
  const [adminEmail, setAdminEmail] = useState('admin@medinet.vn');
  const [systemLanguage, setSystemLanguage] = useState('vi');

  // ─── Security settings state ───
  const [security2FA, setSecurity2FA] = useState(false);
  const [securityTimeout, setSecurityTimeout] = useState('30');

  // ─── Notifications settings state ───
  const [notifyEmail, setNotifyEmail] = useState(true);
  const [notifyTelegram, setNotifyTelegram] = useState(false);

  // ─── MCP domain state (admin set chung cho cả deployment) ───
  // Mặc định suy từ host thật của app (MCP_URL); giá trị admin đã lưu trong
  // DB sẽ override. Profile tab MCP Connector tự fetch giá trị này để mọi
  // user dùng chung domain. Per-user credentials lo ở Profile.
  const [mcpPublicUrl, setMcpPublicUrl] = useState(MCP_URL);

  // RAG config state
  const [ragEmbeddingProvider, setRagEmbeddingProvider] = useState('gemini');
  const [ragEmbeddingModel, setRagEmbeddingModel] = useState('gemini-embedding-001');
  // Remember last chosen model per provider so switching back restores the selection
  const [selectedModelByProvider, setSelectedModelByProvider] = useState<Record<string, string>>({
    gemini: 'gemini-embedding-001',
    openai: 'text-embedding-3-small',
  });
  const [ragChunkSize, setRagChunkSize] = useState(512);
  const [ragChunkOverlap, setRagChunkOverlap] = useState(50);
  const [ragBatchSize, setRagBatchSize] = useState(100);
  const [llmProvider, setLlmProvider] = useState<'gemini' | 'openai' | 'auto'>('auto');
  const [geminiLLMModel, setGeminiLLMModel] = useState('gemini-2.0-flash-lite');
  const [geminiKey, setGeminiKey] = useState('');
  const [openaiKey, setOpenaiKey] = useState('');
  const [geminiKeyMask, setGeminiKeyMask] = useState('');
  const [openaiKeyMask, setOpenaiKeyMask] = useState('');
  // editing=true swaps the masked display for an editable input (pencil button).
  const [editingGemini, setEditingGemini] = useState(false);
  const [editingOpenai, setEditingOpenai] = useState(false);

  // Test connection state
  const [testingGemini, setTestingGemini] = useState(false);
  const [testingOpenai, setTestingOpenai] = useState(false);
  const [geminiTestResult, setGeminiTestResult] = useState<'success' | 'error' | null>(null);
  const [openaiTestResult, setOpenaiTestResult] = useState<'success' | 'error' | null>(null);

  // Collection inventory — lets admin see dimension lock of every hub
  // and warns BEFORE saving a mismatched embedding provider/model.
  interface CollectionInfo {
    hub_code: string;
    hub_name: string;
    collection: string;
    dimension: number;      // 0 = empty (no lock)
    doc_count: number;
    mismatch: boolean;
  }
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [currentDim, setCurrentDim] = useState(0);
  const [loadingCollections, setLoadingCollections] = useState(false);

  const loadCollections = () => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    setLoadingCollections(true);
    fetch(`/api/rag-config/collections`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then(data => {
        if (!data) return;
        setCollections(data.collections || []);
        setCurrentDim(data.current_dimension || 0);
      })
      .catch(() => {})
      .finally(() => setLoadingCollections(false));
  };

  useEffect(() => {
    if (activeTab === 'rag') loadCollections();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, ragEmbeddingProvider, ragEmbeddingModel, saveSuccess]);

  // Load general / security / notification settings
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (!token) return;
    fetch(`/api/system-settings`, {
      headers: { Authorization: `Bearer ${token}` },
    })
      .then(r => r.ok ? r.json() : null)
      .then((data: Record<string, string> | null) => {
        if (!data) return;
        if (data.SYSTEM_NAME)              setSystemName(data.SYSTEM_NAME);
        if (data.SYSTEM_URL)               setSystemUrl(data.SYSTEM_URL);
        if (data.ADMIN_EMAIL)              setAdminEmail(data.ADMIN_EMAIL);
        if (data.SYSTEM_LANGUAGE)          setSystemLanguage(data.SYSTEM_LANGUAGE);
        if (data.SECURITY_2FA_ENABLED)     setSecurity2FA(data.SECURITY_2FA_ENABLED === 'true');
        if (data.SECURITY_SESSION_TIMEOUT) setSecurityTimeout(data.SECURITY_SESSION_TIMEOUT);
        if (data.NOTIFY_EMAIL_ENABLED)     setNotifyEmail(data.NOTIFY_EMAIL_ENABLED === 'true');
        if (data.NOTIFY_TELEGRAM_ENABLED)  setNotifyTelegram(data.NOTIFY_TELEGRAM_ENABLED === 'true');
        if (data.MCP_PUBLIC_URL)           setMcpPublicUrl(data.MCP_PUBLIC_URL);
      })
      .catch(() => {});
  }, []);

  // Load current RAG config
  useEffect(() => {
    fetch(`/api/rag-config`)
      .then(r => r.json())
      .then(data => {
        if (data.embedding_provider) setRagEmbeddingProvider(data.embedding_provider);
        if (data.embedding_model) {
          setRagEmbeddingModel(data.embedding_model);
          if (data.embedding_provider) {
            setSelectedModelByProvider(prev => ({ ...prev, [data.embedding_provider]: data.embedding_model }));
          }
        }
        if (data.chunk_size) setRagChunkSize(data.chunk_size);
        if (data.chunk_overlap) setRagChunkOverlap(data.chunk_overlap);
        if (data.gemini_key_mask) setGeminiKeyMask(data.gemini_key_mask);
        if (data.openai_key_mask) setOpenaiKeyMask(data.openai_key_mask);
        if (data.batch_size) setRagBatchSize(data.batch_size);
        if (data.llm_provider) setLlmProvider(data.llm_provider as 'gemini' | 'openai' | 'auto');
        if (data.gemini_llm_model) setGeminiLLMModel(data.gemini_llm_model);
      })
      .catch(() => {});
  }, []);

  const embeddingModels: Record<string, string[]> = {
    gemini: ['gemini-embedding-001', 'gemini-embedding-2-preview'],
    openai: ['text-embedding-3-small', 'text-embedding-3-large'],
  };

  const tabs = [
    { id: 'general', label: 'Cài đặt chung' },
    { id: 'security', label: 'Bảo mật' },
    { id: 'notifications', label: 'Thông báo' },
    { id: 'mcp', label: 'MCP Connector' },
    { id: 'rag', label: 'Cấu hình RAG' },
  ];

  const saveSystemSettings = async () => {
    const token = localStorage.getItem('access_token');
    const res = await fetch(`/api/system-settings`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        SYSTEM_NAME:              systemName,
        SYSTEM_URL:               systemUrl,
        ADMIN_EMAIL:              adminEmail,
        SYSTEM_LANGUAGE:          systemLanguage,
        SECURITY_2FA_ENABLED:     String(security2FA),
        SECURITY_SESSION_TIMEOUT: securityTimeout,
        NOTIFY_EMAIL_ENABLED:     String(notifyEmail),
        NOTIFY_TELEGRAM_ENABLED:  String(notifyTelegram),
        MCP_PUBLIC_URL:           mcpPublicUrl,
      }),
    });
    return res;
  };

  const saveRAGConfig = async () => {
    const token = localStorage.getItem('access_token');
    const res = await fetch(`/api/rag-config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`,
      },
      body: JSON.stringify({
        embedding_provider: ragEmbeddingProvider,
        embedding_model: ragEmbeddingModel,
        chunk_size: ragChunkSize,
        chunk_overlap: ragChunkOverlap,
        batch_size: ragBatchSize,
        ...(geminiKey && { gemini_api_key: geminiKey }),
        ...(openaiKey && { openai_api_key: openaiKey }),
        llm_provider: llmProvider,
        gemini_llm_model: geminiLLMModel,
      }),
    });
    return res;
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    setSaveError(null);
    try {
      let res: Response;
      if (activeTab === 'rag') {
        res = await saveRAGConfig();
        if (res.ok) {
          // Refresh masks + clear plain keys + exit edit mode
          if (geminiKey) { setGeminiKeyMask(geminiKey.slice(0, 8) + '****' + geminiKey.slice(-4)); setGeminiKey(''); }
          if (openaiKey) { setOpenaiKeyMask(openaiKey.slice(0, 8) + '****' + openaiKey.slice(-4)); setOpenaiKey(''); }
          setEditingGemini(false);
          setEditingOpenai(false);
        }
      } else {
        // general / security / notifications all share the same system-settings endpoint
        res = await saveSystemSettings();
      }
      if (res.ok) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        const body = await res.json().catch(() => ({}));
        setSaveError(body.error || `Lỗi máy chủ (${res.status})`);
        setTimeout(() => setSaveError(null), 5000);
      }
    } catch {
      setSaveError('Không thể kết nối đến máy chủ');
      setTimeout(() => setSaveError(null), 5000);
    }
    setIsSaving(false);
  };

  const handleTestConnection = async (provider: 'gemini' | 'openai') => {
    const setTesting = provider === 'gemini' ? setTestingGemini : setTestingOpenai;
    const setResult = provider === 'gemini' ? setGeminiTestResult : setOpenaiTestResult;
    setTesting(true);
    setResult(null);
    try {
      const res = await fetch(`/api/rag-config/test?provider=${provider}`, {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('access_token')}` },
      });
      setResult(res.ok ? 'success' : 'error');
    } catch {
      setResult('error');
    }
    setTesting(false);
    setTimeout(() => setResult(null), 5000);
  };

  const availableModels = MODEL_CATALOG.filter(m => m.provider === ragEmbeddingProvider);

  // ─── MCP domain — kiểm tra scheme cho cảnh báo HTTPS ───
  // Per-user credentials + URL connector path /mcp đã chuyển sang Profile.
  const mcpBase = mcpPublicUrl.trim().replace(/\/+$/, '');
  const isHttps = mcpBase.toLowerCase().startsWith('https://');

  // Locked dimension = the dimension already stored in non-empty collections.
  // If all non-empty collections share the same dim → that's the lock.
  // If they differ → "mixed" (no single model can satisfy all hubs).
  const nonEmptyDims = Array.from(new Set(
    collections.filter(c => c.dimension > 0).map(c => c.dimension)
  ));
  const lockedDimension: number | 'mixed' | null =
    nonEmptyDims.length === 0 ? null
    : nonEmptyDims.length === 1 ? nonEmptyDims[0]
    : 'mixed';

  // ─── Pipeline steps ───
  const pipelineSteps = [
    { icon: FileText, label: 'Extract', desc: 'Trích xuất' },
    { icon: Layers, label: 'Chunk', desc: 'Chia đoạn' },
    { icon: Sparkles, label: 'Embed', desc: 'Vector hóa' },
    { icon: Database, label: 'Store', desc: 'Lưu trữ' },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-h1 font-semibold text-slate-900 dark:text-white">Cài đặt hệ thống</h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Quản lý cấu hình toàn cục của Medinet Wiki Hub</p>
        </div>
        <div className="flex items-center gap-3">
          <AnimatePresence>
            {saveSuccess && (
              <motion.span
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-1.5 text-xs text-success font-medium bg-success/10 px-3 py-1.5 rounded-full"
              >
                <CheckCircle2 size={14} /> Đã lưu thành công
              </motion.span>
            )}
            {saveError && (
              <motion.span
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 10 }}
                className="flex items-center gap-1.5 text-xs text-red-600 dark:text-red-400 font-medium bg-red-50 dark:bg-red-900/20 px-3 py-1.5 rounded-full"
              >
                <AlertTriangle size={14} /> {saveError}
              </motion.span>
            )}
          </AnimatePresence>
          <button
            onClick={handleSave}
            disabled={isSaving}
            className="btn-primary w-full sm:w-auto"
          >
            {isSaving ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
            <span>{isSaving ? 'Đang lưu...' : 'Lưu thay đổi'}</span>
          </button>
        </div>
      </div>

      <div className="flex flex-col gap-6">
        {/* Tab bar — horizontal underline style */}
        <div className="flex gap-1 border-b border-slate-200 dark:border-slate-700 overflow-x-auto no-scrollbar">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "relative px-3 sm:px-4 py-2.5 sm:py-3 text-xs sm:text-sm font-medium transition-colors whitespace-nowrap",
                activeTab === tab.id
                  ? "text-brand-indigo"
                  : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              )}
            >
              {tab.label}
              {activeTab === tab.id && (
                <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-indigo rounded-full" />
              )}
            </button>
          ))}
        </div>

        {/* Content Area */}
        <div className="min-w-0">
          {/* ═══════════ TAB: General ═══════════ */}
          {activeTab === 'general' && (
            <div className="glass-card p-4 sm:p-8 min-h-[400px] sm:min-h-[500px]">
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-8"
              >
                <div className="space-y-6">
                  <h3 className="text-h2 font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 pb-4">Thông tin hệ thống</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Tên hệ thống</label>
                      <input
                        type="text"
                        value={systemName}
                        onChange={e => setSystemName(e.target.value)}
                        className="input-field w-full"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">URL hệ thống</label>
                      <input
                        type="text"
                        value={systemUrl}
                        onChange={e => setSystemUrl(e.target.value)}
                        className="input-field w-full"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Email quản trị</label>
                      <input
                        type="email"
                        value={adminEmail}
                        onChange={e => setAdminEmail(e.target.value)}
                        className="input-field w-full"
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Ngôn ngữ</label>
                      <select
                        value={systemLanguage}
                        onChange={e => setSystemLanguage(e.target.value)}
                        className="input-field w-full"
                      >
                        <option value="vi">Tiếng Việt</option>
                        <option value="en">English</option>
                      </select>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          )}

          {/* ═══════════ TAB: Security ═══════════ */}
          {activeTab === 'security' && (
            <div className="glass-card p-4 sm:p-8 min-h-[400px] sm:min-h-[500px]">
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-8"
              >
                <div className="space-y-6">
                  <h3 className="text-h2 font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 pb-4">Chính sách bảo mật</h3>
                  <div className="space-y-4">
                    <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-700">
                      <div className="flex items-center gap-4">
                        <Lock size={20} className="text-slate-400" />
                        <div>
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-100">Xác thực 2 bước (2FA)</p>
                          <p className="text-xs text-slate-500">Yêu cầu mã OTP khi đăng nhập</p>
                        </div>
                      </div>
                      <button
                        onClick={() => setSecurity2FA(v => !v)}
                        className={cn(
                          "w-12 h-6 rounded-full relative transition-colors duration-200",
                          security2FA ? "bg-brand-indigo" : "bg-slate-200 dark:bg-slate-700"
                        )}
                      >
                        <div className={cn(
                          "absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200",
                          security2FA ? "right-1" : "left-1"
                        )} />
                      </button>
                    </div>
                    <div className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-700">
                      <div className="flex items-center gap-4">
                        <Eye size={20} className="text-slate-400" />
                        <div>
                          <p className="text-sm font-medium text-slate-800 dark:text-slate-100">Timeout phiên làm việc</p>
                          <p className="text-xs text-slate-500">Tự động đăng xuất sau thời gian không hoạt động</p>
                        </div>
                      </div>
                      <select
                        value={securityTimeout}
                        onChange={e => setSecurityTimeout(e.target.value)}
                        className="input-field w-28 text-sm"
                      >
                        <option value="15">15 phút</option>
                        <option value="30">30 phút</option>
                        <option value="60">1 giờ</option>
                        <option value="240">4 giờ</option>
                        <option value="480">8 giờ</option>
                      </select>
                    </div>
                  </div>
                </div>
              </motion.div>
            </div>
          )}

          {/* ═══════════ TAB: Notifications ═══════════ */}
          {activeTab === 'notifications' && (
            <div className="glass-card p-4 sm:p-8 min-h-[400px] sm:min-h-[500px]">
              <motion.div
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="space-y-8"
              >
                <div className="space-y-6">
                  <h3 className="text-h2 font-semibold text-slate-800 dark:text-slate-100 border-b border-slate-100 dark:border-slate-700 pb-4">Kênh thông báo</h3>
                  <div className="space-y-4">
                    {([
                      {
                        label: 'Thông báo qua Email',
                        desc: 'Gửi báo cáo hàng ngày và cảnh báo hệ thống',
                        icon: Mail,
                        active: notifyEmail,
                        toggle: () => setNotifyEmail(v => !v),
                      },
                      {
                        label: 'Thông báo Telegram',
                        desc: 'Gửi thông báo tức thời khi có lỗi Hub',
                        icon: Smartphone,
                        active: notifyTelegram,
                        toggle: () => setNotifyTelegram(v => !v),
                      },
                    ] as const).map((item, i) => (
                      <div key={i} className="flex items-center justify-between p-4 bg-slate-50 dark:bg-slate-800/50 rounded-2xl border border-slate-100 dark:border-slate-700">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-500 dark:text-slate-400">
                            <item.icon size={20} />
                          </div>
                          <div className="space-y-1">
                            <p className="text-sm font-medium text-slate-800 dark:text-slate-100">{item.label}</p>
                            <p className="text-xs text-slate-500 dark:text-slate-400">{item.desc}</p>
                          </div>
                        </div>
                        <button
                          onClick={item.toggle}
                          className={cn(
                            "w-12 h-6 rounded-full relative transition-colors duration-200",
                            item.active ? "bg-brand-indigo" : "bg-slate-200 dark:bg-slate-700"
                          )}
                        >
                          <div className={cn(
                            "absolute top-1 w-4 h-4 bg-white rounded-full shadow transition-all duration-200",
                            item.active ? "right-1" : "left-1"
                          )} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>
              </motion.div>
            </div>
          )}

          {/* ═══════════ TAB: MCP Connector (admin — cấu hình domain dùng chung) ═══════════ */}
          {activeTab === 'mcp' && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-6"
            >
              {/* ══ Domain config (admin set 1 lần cho cả deployment) ══ */}
              <section className="glass-card p-5 sm:p-6">
                <div className="flex items-center gap-3 mb-5">
                  <div className="w-9 h-9 rounded-xl bg-brand-indigo/10 flex items-center justify-center shrink-0">
                    <Plug size={18} className="text-brand-indigo" />
                  </div>
                  <div>
                    <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100">Domain MCP Service</h3>
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      Cấu hình chung deployment — admin set 1 lần, mọi user dùng. Credentials OAuth riêng từng user xem ở <strong>Profile → MCP Connector</strong>.
                    </p>
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-slate-700 dark:text-slate-200">
                    Domain public HTTPS của MCP Service
                  </label>
                  <input
                    type="text"
                    value={mcpPublicUrl}
                    onChange={e => setMcpPublicUrl(e.target.value)}
                    placeholder={MCP_URL}
                    className="input-field w-full font-mono text-sm"
                    spellCheck={false}
                  />
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    URL gốc nơi MCP Service được expose ra Internet — khớp <code className="font-mono">MCP_OAUTH_ISSUER_URL</code> của container. Để trống thì frontend tự suy từ host đang chạy app. Sửa xong nhấn <strong>Lưu thay đổi</strong> ở góc trên.
                  </p>
                </div>

                {mcpBase && !isHttps && (
                  <div className="mt-3 flex items-start gap-2.5 p-3 bg-warning/10 border border-warning/20 rounded-xl">
                    <AlertTriangle size={14} className="text-warning shrink-0 mt-0.5" />
                    <p className="text-xs text-warning font-medium leading-relaxed">
                      Domain không dùng <strong>https://</strong> — Claude web chỉ chấp nhận connector qua HTTPS, OAuth flow sẽ lỗi nếu để HTTP.
                    </p>
                  </div>
                )}

                <div className="mt-4 flex items-start gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 rounded-xl">
                  <Info size={12} className="text-slate-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    Mỗi user có cặp <strong>client_id / client_secret riêng</strong> (bind cứng theo tài khoản). Vào <strong>Profile → tab MCP Connector</strong> để xem cặp của bạn, sao chép sang dialog "Add custom connector" của Claude web.
                  </p>
                </div>
              </section>
            </motion.div>
          )}

          {/* ═══════════ TAB: RAG Config ═══════════ */}
          {activeTab === 'rag' && (
            <motion.div
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              className="space-y-6"
            >
              {/* ══ SECTION 1 · API KEYS ══ */}
              <section className="glass-card p-5 sm:p-6">
                <SectionHeader
                  number="1"
                  title="API Keys"
                  description="Cấu hình API Keys cho các provider AI."
                />

                <div className="space-y-3">
                  {([
                    {
                      id: 'gemini' as const,
                      label: 'Gemini API Key',
                      placeholder: 'AIzaSy...',
                      mask: geminiKeyMask,
                      value: geminiKey,
                      editing: editingGemini,
                      testing: testingGemini,
                      result: geminiTestResult,
                      setVal: setGeminiKey,
                      setEditing: setEditingGemini,
                    },
                    {
                      id: 'openai' as const,
                      label: 'OpenAI API Key',
                      placeholder: 'sk-proj-...',
                      mask: openaiKeyMask,
                      value: openaiKey,
                      editing: editingOpenai,
                      testing: testingOpenai,
                      result: openaiTestResult,
                      setVal: setOpenaiKey,
                      setEditing: setEditingOpenai,
                    },
                  ] as const).map((k) => (
                    <div
                      key={k.id}
                      className="flex flex-col sm:flex-row sm:items-center gap-3 px-4 py-3 rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/20"
                    >
                      <span className="text-sm font-medium text-slate-700 dark:text-slate-200 sm:w-44 shrink-0">
                        {k.label}
                      </span>
                      <div className="flex-1 min-w-0">
                        {k.editing ? (
                          <input
                            type="text"
                            autoFocus
                            value={k.value}
                            onChange={(e) => k.setVal(e.target.value)}
                            placeholder={`Nhập ${k.label} mới...`}
                            className="input-field w-full font-mono text-sm"
                            autoComplete="new-password"
                            data-lpignore="true"
                            data-form-type="other"
                            data-1p-ignore
                            spellCheck={false}
                          />
                        ) : (
                          <span className="block truncate font-mono text-sm text-slate-500 dark:text-slate-400">
                            {k.mask || <span className="italic text-slate-400">Chưa cấu hình</span>}
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {k.editing ? (
                          <button
                            type="button"
                            onClick={() => { k.setEditing(false); k.setVal(''); }}
                            title="Hủy"
                            className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                          >
                            <X size={16} />
                          </button>
                        ) : (
                          <button
                            type="button"
                            onClick={() => k.setEditing(true)}
                            title="Sửa / đổi API key"
                            className="w-9 h-9 flex items-center justify-center rounded-lg text-slate-400 hover:text-brand-indigo hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                          >
                            <Pencil size={15} />
                          </button>
                        )}
                        <button
                          onClick={() => handleTestConnection(k.id)}
                          disabled={k.testing || (!k.mask && !k.value)}
                          className={cn(
                            "btn-secondary !px-4 min-h-[38px] text-xs",
                            k.result === 'success' && '!border-success !text-success',
                            k.result === 'error' && '!border-danger !text-danger',
                          )}
                        >
                          {k.testing ? 'Đang test…'
                            : k.result === 'success' ? 'OK'
                            : k.result === 'error' ? 'Lỗi'
                            : 'Test'}
                        </button>
                      </div>
                    </div>
                  ))}
                </div>

                {/* Warning when active embedding provider has no key */}
                {((ragEmbeddingProvider === 'gemini' && !geminiKeyMask && !geminiKey) ||
                  (ragEmbeddingProvider === 'openai' && !openaiKeyMask && !openaiKey)) && (
                  <div className="mt-3 flex items-start gap-2.5 p-3 bg-warning/10 border border-warning/20 rounded-xl">
                    <AlertTriangle size={14} className="text-warning shrink-0 mt-0.5" />
                    <p className="text-xs text-warning font-medium leading-relaxed">
                      Embedding đang chọn <strong>{ragEmbeddingProvider === 'gemini' ? 'Gemini' : 'OpenAI'}</strong> nhưng chưa có API key — tài liệu sẽ không được vector hóa.
                    </p>
                  </div>
                )}
              </section>

              {/* ══ SECTION 2 · KHI NẠP TÀI LIỆU MỚI ══ */}
              <section className="glass-card p-5 sm:p-6">
                <SectionHeader
                  number="2"
                  title="Khi nạp tài liệu mới"
                  badgeText="INGEST-TIME"
                  description="Cấu hình vector hóa (embedding) khi thêm tài liệu vào hệ thống."
                />

                <div className="space-y-4">
                  {/* ── Embedding sub-card ── */}
                  <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 sm:gap-5">
                      {/* Provider */}
                      <div className="space-y-1.5">
                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">Provider</label>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Chọn provider</p>
                        <select
                          value={ragEmbeddingProvider}
                          onChange={(e) => {
                            const p = e.target.value;
                            setRagEmbeddingProvider(p);
                            setRagEmbeddingModel(selectedModelByProvider[p] || embeddingModels[p]?.[0] || '');
                          }}
                          className="input-field w-full"
                        >
                          <option value="gemini">Google Gemini</option>
                          <option value="openai">OpenAI</option>
                        </select>
                      </div>
                      {/* Model */}
                      <div className="space-y-1.5">
                        <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">Model</label>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Chọn model</p>
                        <select
                          value={ragEmbeddingModel}
                          onChange={(e) => {
                            setRagEmbeddingModel(e.target.value);
                            setSelectedModelByProvider(prev => ({ ...prev, [ragEmbeddingProvider]: e.target.value }));
                          }}
                          className="input-field w-full"
                        >
                          {availableModels.map((m) => (
                            <option key={m.id} value={m.id}>{m.id}</option>
                          ))}
                        </select>
                      </div>
                    </div>

                    {/* Active mismatch warning */}
                    {typeof lockedDimension === 'number' && ragEmbeddingModel && (() => {
                      const activeModel = MODEL_CATALOG.find(m => m.id === ragEmbeddingModel);
                      if (!activeModel || activeModel.dimension === lockedDimension) return null;
                      const compatibleModels = MODEL_CATALOG.filter(m => m.dimension === lockedDimension).map(m => m.id);
                      return (
                        <div className="mt-4 flex items-start gap-2 p-3 bg-danger/10 border border-danger/30 rounded-xl">
                          <AlertTriangle size={14} className="text-danger shrink-0 mt-0.5" />
                          <div className="space-y-1 min-w-0">
                            <p className="text-xs font-semibold text-danger">
                              Model đang chọn sinh vector <span className="font-mono">{activeModel.dimension}d</span>, nhưng các hub đang lưu <span className="font-mono">{lockedDimension}d</span>.
                            </p>
                            <p className="text-[11px] text-danger/90 leading-relaxed">
                              Lưu config này sẽ làm <strong>hỏng mọi search + upload</strong> trên các hub đã có dữ liệu. Chọn một model có {lockedDimension}d (ví dụ: <span className="font-mono">{compatibleModels.join(', ')}</span>) hoặc xóa collection của hub để re-embed từ đầu.
                            </p>
                          </div>
                        </div>
                      );
                    })()}

                    {/* Batch size */}
                    <div className="space-y-1.5 mt-4 sm:mt-5">
                      <label className="text-sm font-semibold text-slate-700 dark:text-slate-200">Batch Size</label>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Số chunks gửi mỗi lần gọi Embedding API</p>
                      <div className="relative">
                        <input
                          type="number"
                          min={1}
                          max={500}
                          value={ragBatchSize}
                          onChange={(e) => setRagBatchSize(Number(e.target.value))}
                          className="input-field w-full pr-24"
                        />
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-slate-400 dark:text-slate-500 pointer-events-none">
                          chunks/call
                        </span>
                      </div>
                    </div>

                    {/* Dimension warning */}
                    <div className="mt-4 flex items-start gap-2 p-3 bg-slate-100/70 dark:bg-slate-800/40 border border-slate-200 dark:border-slate-700 rounded-xl">
                      <AlertTriangle size={13} className="text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-[11px] text-slate-600 dark:text-slate-300 leading-relaxed">
                        <strong>Cảnh báo dimension:</strong> ChromaDB khóa dimension vào lần đầu tiên lưu. Đổi provider/model sang vector khác chiều sẽ làm <strong>hỏng search</strong> trên tài liệu cũ — cần xóa collection rồi re-embed.
                      </p>
                    </div>

                    {/* Collection inventory — per-hub dimension visibility */}
                    <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-700">
                      <div className="flex items-center justify-between mb-2.5">
                        <div>
                          <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">
                            Hiện trạng ChromaDB
                          </p>
                          <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-0.5">
                            Provider hiện tại sinh vector {currentDim > 0 ? <span className="font-mono font-semibold">{currentDim}d</span> : '—'} — mỗi hub cần khớp dimension.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={loadCollections}
                          disabled={loadingCollections}
                          className="text-[10px] text-brand-indigo hover:text-brand-purple disabled:opacity-50 flex items-center gap-1"
                        >
                          <RefreshCw size={10} className={loadingCollections ? 'animate-spin' : ''} />
                          Refresh
                        </button>
                      </div>

                      {collections.length === 0 ? (
                        <p className="text-[11px] text-slate-400 dark:text-slate-500 italic py-2">
                          {loadingCollections ? 'Đang tải...' : 'Chưa có hub nào hoặc chưa có quyền admin.'}
                        </p>
                      ) : (
                        <div className="space-y-1.5">
                          {collections.map(col => {
                            const isEmpty = col.dimension === 0;
                            return (
                              <div
                                key={col.hub_code}
                                className={cn(
                                  'flex items-center justify-between gap-2 px-3 py-2 rounded-lg border text-[11px]',
                                  col.mismatch
                                    ? 'border-danger/40 bg-danger/5 dark:bg-danger/10'
                                    : isEmpty
                                    ? 'border-slate-200 dark:border-slate-700 bg-slate-50/60 dark:bg-slate-800/30'
                                    : 'border-success/30 bg-success/5 dark:bg-success/10'
                                )}
                              >
                                <div className="flex items-center gap-2 min-w-0">
                                  <div className={cn(
                                    'w-6 h-6 rounded flex items-center justify-center shrink-0',
                                    col.mismatch ? 'bg-danger/15 text-danger'
                                      : isEmpty ? 'bg-slate-200 dark:bg-slate-700 text-slate-500'
                                      : 'bg-success/15 text-success'
                                  )}>
                                    {col.mismatch ? <AlertTriangle size={11} /> : isEmpty ? <Database size={11} /> : <Check size={11} />}
                                  </div>
                                  <div className="min-w-0">
                                    <p className="font-semibold text-slate-700 dark:text-slate-200 truncate">{col.hub_name}</p>
                                    <p className="font-mono text-[10px] text-slate-400 truncate">{col.collection}</p>
                                  </div>
                                </div>
                                <div className="flex items-center gap-2 shrink-0">
                                  <span className={cn(
                                    'font-mono font-semibold px-1.5 py-0.5 rounded',
                                    isEmpty ? 'bg-slate-200 dark:bg-slate-700 text-slate-500'
                                      : col.mismatch ? 'bg-danger/10 text-danger'
                                      : 'bg-success/10 text-success'
                                  )}>
                                    {isEmpty ? 'trống' : `${col.dimension}d`}
                                  </span>
                                  <span className="text-slate-400 font-mono">
                                    {col.doc_count > 0 ? `${col.doc_count} docs` : '0'}
                                  </span>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      )}

                      {/* Aggregate mismatch warning */}
                      {collections.some(c => c.mismatch) && (
                        <div className="mt-2.5 flex items-start gap-2 p-2.5 bg-danger/10 border border-danger/30 rounded-lg">
                          <AlertTriangle size={12} className="text-danger shrink-0 mt-0.5" />
                          <p className="text-[11px] text-danger font-medium leading-relaxed">
                            Có {collections.filter(c => c.mismatch).length} hub có vector KHÔNG khớp với provider/model đang chọn — nạp tài liệu mới sẽ lỗi, search cũng sẽ lỗi. Đổi về đúng dimension hoặc xóa collection của hub đó.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>

                  {/* ── Chunking sub-card ── */}
                  <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
                    <div className="flex items-center gap-3 mb-5">
                      <div className="w-9 h-9 rounded-xl bg-brand-indigo/10 flex items-center justify-center shrink-0">
                        <Layers size={18} className="text-brand-indigo" />
                      </div>
                      <div>
                        <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100">Chia đoạn (Chunking)</h3>
                        <p className="text-xs text-slate-500 dark:text-slate-400">Cắt tài liệu thành từng đoạn để AI truy xuất chính xác.</p>
                      </div>
                    </div>

                    {/* Pipeline viz */}
                    <div className="flex items-center justify-between p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700 mb-5 overflow-x-auto">
                      {pipelineSteps.map((step, idx) => (
                        <React.Fragment key={step.label}>
                          <div className="flex flex-col items-center gap-1 min-w-[64px]">
                            <div className="w-9 h-9 rounded-lg bg-white dark:bg-slate-700 border border-slate-200 dark:border-slate-600 flex items-center justify-center shadow-sm">
                              <step.icon size={16} className="text-brand-indigo" />
                            </div>
                            <span className="text-[10px] font-semibold text-slate-700 dark:text-slate-200">{step.label}</span>
                          </div>
                          {idx < pipelineSteps.length - 1 && (
                            <ArrowRight size={14} className="text-slate-300 dark:text-slate-600 shrink-0 mx-0.5" />
                          )}
                        </React.Fragment>
                      ))}
                    </div>

                    {/* Sliders */}
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Chunk Size</label>
                          <span className="text-sm font-mono font-semibold text-brand-indigo">{ragChunkSize} tokens</span>
                        </div>
                        <input
                          type="range"
                          min={100}
                          max={4000}
                          step={50}
                          value={ragChunkSize}
                          onChange={(e) => setRagChunkSize(Number(e.target.value))}
                          className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-brand-indigo"
                        />
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          ~{(ragChunkSize * 4).toLocaleString()} ký tự / chunk
                        </p>
                      </div>

                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <label className="text-sm font-medium text-slate-700 dark:text-slate-200">Chunk Overlap</label>
                          <span className="text-sm font-mono font-semibold text-brand-purple">{ragChunkOverlap} tokens</span>
                        </div>
                        <input
                          type="range"
                          min={0}
                          max={500}
                          step={10}
                          value={ragChunkOverlap}
                          onChange={(e) => setRagChunkOverlap(Number(e.target.value))}
                          className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full appearance-none cursor-pointer accent-brand-purple"
                        />
                        <p className="text-[11px] text-slate-500 dark:text-slate-400">
                          ~{(ragChunkOverlap * 4).toLocaleString()} ký tự overlap
                        </p>
                      </div>
                    </div>

                    {/* Separators */}
                    <div className="mt-5 pt-4 border-t border-slate-100 dark:border-slate-700 space-y-2">
                      <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500">Markdown Separators</label>
                      <div className="flex flex-wrap gap-1.5">
                        {SEPARATORS.map((sep, i) => (
                          <span
                            key={i}
                            className="inline-flex items-center gap-1 text-[10px] font-medium bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300 px-2 py-0.5 rounded-full border border-slate-200 dark:border-slate-600"
                          >
                            {i > 0 && <ArrowRight size={8} className="text-slate-400 -ml-0.5" />}
                            {sep}
                          </span>
                        ))}
                      </div>
                      <p className="text-[10px] text-slate-400 flex items-center gap-1">
                        <Info size={9} className="shrink-0" />
                        tiktoken cl100k_base (99% chính xác)
                      </p>
                    </div>
                  </div>
                </div>
              </section>

              {/* ══ SECTION 3 · KHI TÌM KIẾM & TRẢ LỜI ══ */}
              <section className="glass-card p-5 sm:p-6">
                <SectionHeader
                  number="3"
                  title="Khi tìm kiếm & trả lời"
                  badgeText="QUERY-TIME"
                  description="Áp dụng ngay cho mọi search mới — hot-swap, không cần restart server."
                />

                <div className="rounded-xl border border-slate-200 dark:border-slate-700 p-4 sm:p-5">
                  <div className="flex items-center gap-3 mb-5">
                    <div className="w-9 h-9 rounded-xl bg-emerald-500/10 flex items-center justify-center shrink-0">
                      <Cpu size={18} className="text-emerald-600" />
                    </div>
                    <div>
                      <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100">LLM Chat Provider</h3>
                      <p className="text-xs text-slate-500 dark:text-slate-400">Mô hình AI sinh câu trả lời từ tài liệu đã tìm được.</p>
                    </div>
                  </div>

                  {/* Provider picker — 3 modes */}
                  <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 mb-2">
                    Chế độ
                  </p>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mb-5">
                    {([
                      { id: 'gemini' as const, label: 'Gemini Only', desc: 'Chỉ dùng Gemini. Không fallback.', icon: 'G', color: 'blue' },
                      { id: 'openai' as const, label: 'OpenAI Only', desc: 'Chỉ dùng OpenAI. Không fallback.', icon: 'O', color: 'emerald' },
                      { id: 'auto' as const, label: 'Auto (Smart)', desc: 'Gemini trước — OpenAI fallback khi lỗi.', icon: '⚡', color: 'accent' },
                    ] as const).map((opt) => (
                      <button
                        key={opt.id}
                        onClick={() => setLlmProvider(opt.id)}
                        className={cn(
                          "relative flex flex-col items-start gap-1.5 p-3.5 rounded-2xl border-2 transition-all duration-200 text-left",
                          llmProvider === opt.id
                            ? opt.color === 'blue' ? "border-blue-500 bg-blue-50 dark:bg-blue-900/20"
                              : opt.color === 'emerald' ? "border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20"
                              : "border-accent bg-accent/5 dark:bg-accent/10"
                            : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600"
                        )}
                      >
                        {llmProvider === opt.id && (
                          <div className={cn(
                            "absolute top-2.5 right-2.5 w-5 h-5 rounded-full flex items-center justify-center",
                            opt.color === 'blue' ? "bg-blue-500" : opt.color === 'emerald' ? "bg-emerald-500" : "bg-accent"
                          )}>
                            <Check size={11} className="text-white" />
                          </div>
                        )}
                        <div className={cn(
                          "w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold",
                          opt.color === 'blue' ? "bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400"
                            : opt.color === 'emerald' ? "bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30 dark:text-emerald-400"
                            : "bg-accent/10 text-accent"
                        )}>
                          {opt.icon}
                        </div>
                        <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">{opt.label}</span>
                        <span className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">{opt.desc}</span>
                      </button>
                    ))}
                  </div>

                  {/* Gemini Chat Model selector (when Gemini is in the loop) */}
                  {(llmProvider === 'gemini' || llmProvider === 'auto') && (
                    <div className="pt-4 border-t border-slate-100 dark:border-slate-700">
                      <label className="text-[11px] font-semibold uppercase tracking-wide text-slate-400 dark:text-slate-500 block mb-2">
                        Gemini Chat Model
                      </label>
                      <select
                        className="input-field w-full text-sm font-mono"
                        value={geminiLLMModel}
                        onChange={e => setGeminiLLMModel(e.target.value)}
                      >
                        <option value="gemini-2.5-flash">gemini-2.5-flash · GA · khuyến nghị</option>
                        <option value="gemini-2.5-flash-lite">gemini-2.5-flash-lite · GA · nhanh · rẻ</option>
                        <option value="gemini-2.0-flash">gemini-2.0-flash · GA · ổn định</option>
                        <option value="gemini-2.0-flash-lite">gemini-2.0-flash-lite · GA · miễn phí</option>
                        <option value="gemini-2.5-pro">gemini-2.5-pro · mạnh nhất · tốn phí</option>
                      </select>
                      <p className="mt-1.5 text-[10px] text-slate-400 dark:text-slate-500">
                        Gemini ngừng hỗ trợ <code className="font-mono">gemini-2.0-flash</code> cho API key mới. Nếu gặp lỗi 404, đổi sang model khác ở đây.
                      </p>
                    </div>
                  )}

                  {/* Independence note */}
                  <div className="mt-4 flex items-start gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 rounded-xl">
                    <Info size={12} className="text-slate-400 shrink-0 mt-0.5" />
                    <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                      LLM Chat <strong>độc lập</strong> với Embedding: bạn có thể embed bằng Gemini (miễn phí) và chat bằng OpenAI (chất lượng cao), hoặc ngược lại.
                    </p>
                  </div>
                </div>
              </section>
            </motion.div>
          )}
        </div>
      </div>

      {/* Sticky save button on mobile */}
      <div className="fixed bottom-0 left-0 right-0 p-4 bg-white/80 dark:bg-slate-900/80 backdrop-blur-lg border-t border-slate-200 dark:border-slate-700 sm:hidden z-40">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="btn-primary w-full"
        >
          {isSaving ? <RefreshCw size={18} className="animate-spin" /> : <Save size={18} />}
          <span>{isSaving ? 'Đang lưu...' : 'Lưu thay đổi'}</span>
        </button>
      </div>
    </div>
  );
}
