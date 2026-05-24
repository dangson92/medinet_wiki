import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Camera, Save, RefreshCw, Eye, EyeOff, Check, Loader2, AlertCircle, Plug, Copy, Info } from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../services/api';
import type { MCPOAuthClientAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

// URL gốc MCP Service — mặc định suy từ host thật của app (port 8190 dev),
// override qua VITE_MCP_URL khi build. Admin có thể set `MCP_PUBLIC_URL`
// trong Settings → MCP Connector để override per-deployment; Profile fetch
// giá trị đó, fallback về MCP_URL derived nếu admin chưa set.
const MCP_URL = import.meta.env.VITE_MCP_URL || `http://${window.location.hostname}:8190`;
// Phase 5 PROXY-02 fix: dùng absolute path /api/* — Caddy `/api/*` → central.
// system-settings là central-only endpoint (strip ở hub con). KHÔNG dùng API_BASE prefix.

export default function Profile() {
  const { refreshUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'password' | 'mcp'>('info');

  // ─── MCP Connector (Phase 8.3 per-user) ───
  // Lazy-load khi user vào tab MCP. Trả full client_secret plaintext để
  // user copy dán vào dialog Claude → Advanced.
  const [mcpClient, setMcpClient] = useState<MCPOAuthClientAPI | null>(null);
  const [mcpLoading, setMcpLoading] = useState(false);
  const [mcpError, setMcpError] = useState('');
  const [mcpRotating, setMcpRotating] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  // Admin-set domain override từ system-settings (Settings tab → MCP Connector).
  // Rỗng = chưa set → fallback MCP_URL derived từ host.
  const [adminMcpUrl, setAdminMcpUrl] = useState('');

  const [form, setForm] = useState({
    name: '',
    email: '',
    phone: '',
    role: '',
    department: '',
  });

  // Password form
  const [pwForm, setPwForm] = useState({ old_password: '', new_password: '', confirm_password: '' });
  const [pwSaving, setPwSaving] = useState(false);
  const [pwSuccess, setPwSuccess] = useState(false);
  const [pwError, setPwError] = useState('');

  // Load profile from API
  useEffect(() => {
    const fetchProfile = async () => {
      try {
        const res = await api.getProfile();
        if (res.success && res.data) {
          const u = res.data.user;
          const roles = res.data.roles;
          const roleLabel = roles.length > 0 ? roles.map(r => r.role).join(', ') : 'viewer';
          setForm({
            name: u.name || '',
            email: u.email || '',
            phone: u.phone || '',
            role: roleLabel,
            department: u.department || '',
          });
        }
      } catch (err) {
        console.error('Failed to load profile:', err);
      } finally {
        setLoading(false);
      }
    };
    fetchProfile();
  }, []);

  const handleChange = (field: string, value: string) => {
    setForm(prev => ({ ...prev, [field]: value }));
    setSaved(false);
    setError('');
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError('');
    try {
      const res = await api.updateProfile({
        name: form.name,
        phone: form.phone,
        department: form.department,
      });
      if (res.success) {
        setSaved(true);
        setTimeout(() => setSaved(false), 3000);
        refreshUser();
      } else {
        setError(res.error?.message || 'Lưu thất bại');
      }
    } catch (err) {
      setError('Lỗi kết nối server');
    } finally {
      setIsSaving(false);
    }
  };

  const handleChangePassword = async () => {
    setPwError('');
    if (pwForm.new_password !== pwForm.confirm_password) {
      setPwError('Mật khẩu xác nhận không khớp');
      return;
    }
    if (pwForm.new_password.length < 8) {
      setPwError('Mật khẩu mới phải có ít nhất 8 ký tự');
      return;
    }
    setPwSaving(true);
    try {
      const res = await api.changePassword(pwForm.old_password, pwForm.new_password);
      if (res.success) {
        setPwSuccess(true);
        setPwForm({ old_password: '', new_password: '', confirm_password: '' });
        setTimeout(() => setPwSuccess(false), 3000);
      } else {
        setPwError(res.error?.message || 'Đổi mật khẩu thất bại');
      }
    } catch (err) {
      setPwError('Lỗi kết nối server');
    } finally {
      setPwSaving(false);
    }
  };

  // Lazy-load MCP client lần đầu khi user mở tab MCP — KHÔNG fetch ở mount
  // để khỏi tạo cặp cho user chưa cần. Cùng lúc fetch admin-set domain
  // (system-settings) để derive connector URL khớp với deployment.
  useEffect(() => {
    if (activeTab !== 'mcp' || mcpClient || mcpLoading) return;
    setMcpLoading(true);
    setMcpError('');

    // Fetch song song: client per-user + admin MCP domain override.
    const token = localStorage.getItem('access_token');
    const settingsP = token
      ? fetch('/api/system-settings', {
          headers: { Authorization: `Bearer ${token}` },
        })
          .then(r => (r.ok ? r.json() : null))
          .then((data: Record<string, string> | null) => {
            if (data && data.MCP_PUBLIC_URL) setAdminMcpUrl(data.MCP_PUBLIC_URL);
          })
          .catch(() => {})
      : Promise.resolve();

    const clientP = api.getMyMCPOAuthClient()
      .then(res => {
        if (res.success && res.data) setMcpClient(res.data);
        else setMcpError(res.error?.message || 'Không tải được MCP client');
      })
      .catch(() => setMcpError('Lỗi kết nối server'));

    Promise.all([settingsP, clientP]).finally(() => setMcpLoading(false));
  }, [activeTab, mcpClient, mcpLoading]);

  const handleRotateMcpClient = async () => {
    setMcpRotating(true);
    setMcpError('');
    try {
      const res = await api.rotateMyMCPOAuthClient();
      if (res.success && res.data) {
        setMcpClient(res.data);
        setShowSecret(true);  // hiện secret mới ngay để user thấy + copy.
      } else {
        setMcpError(res.error?.message || 'Xoay secret thất bại');
      }
    } catch {
      setMcpError('Lỗi kết nối server');
    } finally {
      setMcpRotating(false);
    }
  };

  const copyToClipboard = (key: string, value: string) => {
    navigator.clipboard?.writeText(value)
      .then(() => {
        setCopiedKey(key);
        setTimeout(() => setCopiedKey(null), 2000);
      })
      .catch(() => {});
  };

  // Derived URL connector — admin override (system setting MCP_PUBLIC_URL)
  // ưu tiên; fallback MCP_URL derived từ host. Transport path cố định `/mcp`.
  // Nếu admin URL ĐÃ kết thúc `/mcp` (path-based deploy, vd
  // `wiki.example.com/mcp`) thì KHÔNG append nữa → tránh `/mcp/mcp` thừa.
  const mcpBase = (adminMcpUrl || MCP_URL).trim().replace(/\/+$/, '');
  const connectorUrl = mcpBase
    ? (mcpBase.toLowerCase().endsWith('/mcp') ? mcpBase : `${mcpBase}/mcp`)
    : '';

  const initials = form.name ? form.name.split(' ').map(w => w[0]).join('').slice(0, 2).toUpperCase() : 'U';

  if (loading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 className="animate-spin text-accent" size={28} />
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-h1 font-bold text-slate-900 dark:text-white tracking-tight">Thông tin cá nhân</h1>
        <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Cập nhật thông tin tài khoản quản trị của bạn</p>
      </div>

      {/* Avatar section */}
      <div className="glass-card p-4 sm:p-6">
        <div className="flex items-center gap-4 sm:gap-5">
          <div className="relative group">
            <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full bg-brand-indigo text-white flex items-center justify-center text-xl sm:text-2xl font-bold">
              {initials}
            </div>
            <button className="absolute inset-0 rounded-full bg-slate-900/50 text-white flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
              <Camera size={20} />
            </button>
          </div>
          <div className="flex-1 min-w-0">
            <h2 className="text-h3 font-bold text-slate-900 dark:text-white">{form.name}</h2>
            <p className="text-sm text-slate-500 dark:text-slate-400">{form.email}</p>
            <p className="text-xs text-slate-400 dark:text-slate-500 mt-1">
              <span className="inline-flex items-center gap-1 px-2 py-0.5 bg-brand-indigo/10 text-brand-indigo rounded-full text-[10px] font-semibold">
                {form.role}
              </span>
            </p>
          </div>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 dark:border-slate-700 gap-1">
        {[
          { id: 'info' as const, label: 'Thông tin chung' },
          { id: 'password' as const, label: 'Đổi mật khẩu' },
          { id: 'mcp' as const, label: 'MCP Connector' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "relative px-4 py-2.5 text-sm font-medium transition-colors",
              activeTab === tab.id ? "text-brand-indigo" : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
            )}
          >
            {tab.label}
            {activeTab === tab.id && (
              <motion.div layoutId="profileTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-brand-indigo" />
            )}
          </button>
        ))}
      </div>

      {/* Content */}
      {activeTab === 'info' && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 sm:p-6 space-y-5"
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Họ và tên</label>
              <input
                type="text"
                value={form.name}
                onChange={(e) => handleChange('name', e.target.value)}
                className="input-field w-full"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Email</label>
              <input
                type="email"
                value={form.email}
                disabled
                className="input-field w-full bg-slate-50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 cursor-not-allowed"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Số điện thoại</label>
              <input
                type="text"
                value={form.phone}
                onChange={(e) => handleChange('phone', e.target.value)}
                className="input-field w-full"
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Phòng ban</label>
              <input
                type="text"
                value={form.department}
                onChange={(e) => handleChange('department', e.target.value)}
                className="input-field w-full"
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Vai trò</label>
            <input
              type="text"
              value={form.role}
              disabled
              className="input-field w-full bg-slate-50 dark:bg-slate-800/50 text-slate-400 dark:text-slate-500 cursor-not-allowed"
            />
            <p className="text-xs text-slate-400 dark:text-slate-500">Vai trò được cấp bởi hệ thống, không thể tự thay đổi.</p>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-sm text-danger bg-danger/10 px-3 py-2 rounded-lg">
              <AlertCircle size={16} /> {error}
            </div>
          )}

          <div className="flex items-center justify-end gap-3 pt-2">
            {saved && (
              <motion.span
                initial={{ opacity: 0, x: 10 }}
                animate={{ opacity: 1, x: 0 }}
                className="text-sm text-success flex items-center gap-1"
              >
                <Check size={16} /> Đã lưu
              </motion.span>
            )}
            <button
              onClick={handleSave}
              disabled={isSaving}
              className="btn-primary"
            >
              {isSaving ? <RefreshCw size={16} className="animate-spin" /> : <Save size={16} />}
              {isSaving ? 'Đang lưu...' : 'Lưu thay đổi'}
            </button>
          </div>
        </motion.div>
      )}

      {activeTab === 'password' && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-4 sm:p-6 space-y-5"
        >
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mật khẩu hiện tại</label>
            <div className="relative">
              <input
                type={showOldPassword ? 'text' : 'password'}
                placeholder="Nhập mật khẩu hiện tại"
                value={pwForm.old_password}
                onChange={(e) => { setPwForm(p => ({ ...p, old_password: e.target.value })); setPwError(''); }}
                className="input-field w-full pr-10"
              />
              <button
                type="button"
                onClick={() => setShowOldPassword(!showOldPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              >
                {showOldPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mật khẩu mới</label>
            <div className="relative">
              <input
                type={showNewPassword ? 'text' : 'password'}
                placeholder="Nhập mật khẩu mới"
                value={pwForm.new_password}
                onChange={(e) => { setPwForm(p => ({ ...p, new_password: e.target.value })); setPwError(''); }}
                className="input-field w-full pr-10"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
              >
                {showNewPassword ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Xác nhận mật khẩu mới</label>
            <input
              type="password"
              placeholder="Nhập lại mật khẩu mới"
              value={pwForm.confirm_password}
              onChange={(e) => { setPwForm(p => ({ ...p, confirm_password: e.target.value })); setPwError(''); }}
              className="input-field w-full"
            />
          </div>

          <div className="p-3 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700 space-y-1">
            <p className="text-xs font-medium text-slate-600 dark:text-slate-300">Yêu cầu mật khẩu:</p>
            <ul className="text-xs text-slate-400 dark:text-slate-500 space-y-0.5 list-disc list-inside">
              <li>Tối thiểu 8 ký tự</li>
              <li>Ít nhất 1 chữ hoa và 1 chữ thường</li>
              <li>Ít nhất 1 số hoặc ký tự đặc biệt</li>
            </ul>
          </div>

          {pwError && (
            <div className="flex items-center gap-2 text-sm text-danger bg-danger/10 px-3 py-2 rounded-lg">
              <AlertCircle size={16} /> {pwError}
            </div>
          )}

          {pwSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -4 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex items-center gap-2 text-sm text-success bg-success/10 px-3 py-2 rounded-lg"
            >
              <Check size={16} /> Đổi mật khẩu thành công
            </motion.div>
          )}

          <div className="flex justify-end pt-2">
            <button
              onClick={handleChangePassword}
              disabled={pwSaving || !pwForm.old_password || !pwForm.new_password || !pwForm.confirm_password}
              className="btn-primary"
            >
              {pwSaving ? <RefreshCw size={16} className="animate-spin" /> : null}
              {pwSaving ? 'Đang xử lý...' : 'Đổi mật khẩu'}
            </button>
          </div>
        </motion.div>
      )}

      {activeTab === 'mcp' && (
        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="space-y-6"
        >
          {/* ═══════════ Card 1 — MCP Endpoint URL ═══════════ */}
          <div className="glass-card p-4 sm:p-6">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-9 h-9 rounded-xl bg-brand-indigo/10 flex items-center justify-center shrink-0">
                <Plug size={18} className="text-brand-indigo" />
              </div>
              <div>
                <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100">MCP Connector cho Claude</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400">
                  Kết nối Claude web tới Medinet Wiki bằng tài khoản của bạn — credentials riêng từng user.
                </p>
              </div>
            </div>

            <div className="rounded-xl border border-brand-indigo/40 bg-brand-indigo/5 dark:bg-brand-indigo/10 p-3.5">
              <div className="flex items-center justify-between gap-2 mb-1.5">
                <span className="text-sm font-semibold text-slate-700 dark:text-slate-200">MCP Endpoint URL</span>
                <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded text-brand-indigo bg-brand-indigo/10 shrink-0">
                  Dán vào ô URL
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mb-2 leading-relaxed">
                URL chính cho dialog "Add custom connector" của Claude web.
              </p>
              <div className="flex items-center gap-2">
                <code className="flex-1 min-w-0 truncate font-mono text-xs sm:text-sm px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200">
                  {connectorUrl}
                </code>
                <button
                  type="button"
                  onClick={() => copyToClipboard('connector', connectorUrl)}
                  title="Sao chép"
                  className={cn(
                    'w-9 h-9 flex items-center justify-center rounded-lg shrink-0 transition-colors',
                    copiedKey === 'connector'
                      ? 'text-success bg-success/10'
                      : 'text-slate-400 hover:text-brand-indigo hover:bg-slate-100 dark:hover:bg-slate-700',
                  )}
                >
                  {copiedKey === 'connector' ? <Check size={16} /> : <Copy size={15} />}
                </button>
              </div>
            </div>
          </div>

          {/* ═══════════ Card 2 — Per-user OAuth credentials ═══════════ */}
          <div className="glass-card p-4 sm:p-6">
            <div className="flex items-center justify-between gap-3 mb-4 flex-wrap">
              <div>
                <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100">OAuth Client của tôi</h3>
                <p className="text-xs text-slate-500 dark:text-slate-400 mt-1 leading-relaxed">
                  Cặp client_id/secret riêng của tài khoản này — bind cứng theo user. Mở Advanced trong dialog Claude rồi dán.
                </p>
              </div>
              <button
                type="button"
                onClick={handleRotateMcpClient}
                disabled={mcpRotating || mcpLoading}
                className="btn-secondary !px-3 text-xs whitespace-nowrap"
                title="Sinh client_secret mới (giữ client_id)"
              >
                {mcpRotating ? <RefreshCw size={14} className="animate-spin" /> : <RefreshCw size={14} />}
                {mcpRotating ? 'Đang xoay...' : 'Xoay secret'}
              </button>
            </div>

            {mcpLoading && !mcpClient && (
              <div className="flex items-center gap-2 py-6 justify-center text-slate-400">
                <Loader2 size={18} className="animate-spin" />
                <span className="text-sm">Đang tải credentials…</span>
              </div>
            )}

            {mcpError && (
              <div className="flex items-start gap-2 text-sm text-danger bg-danger/10 px-3 py-2 rounded-lg mb-3">
                <AlertCircle size={16} className="shrink-0 mt-0.5" /> {mcpError}
              </div>
            )}

            {mcpClient && (
              <div className="space-y-3">
                {/* Client ID — không nhạy cảm */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/20 p-3.5">
                  <label className="text-sm font-semibold text-slate-700 dark:text-slate-200 block mb-1.5">
                    OAuth Client ID
                  </label>
                  <div className="flex items-center gap-2">
                    <code className="flex-1 min-w-0 truncate font-mono text-xs sm:text-sm px-3 py-2 rounded-lg bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200">
                      {mcpClient.client_id}
                    </code>
                    <button
                      type="button"
                      onClick={() => copyToClipboard('client-id', mcpClient.client_id)}
                      title="Sao chép"
                      className={cn(
                        'w-9 h-9 flex items-center justify-center rounded-lg shrink-0 transition-colors',
                        copiedKey === 'client-id'
                          ? 'text-success bg-success/10'
                          : 'text-slate-400 hover:text-brand-indigo hover:bg-slate-100 dark:hover:bg-slate-700',
                      )}
                    >
                      {copiedKey === 'client-id' ? <Check size={16} /> : <Copy size={15} />}
                    </button>
                  </div>
                </div>

                {/* Client Secret — nhạy cảm, mặc định che */}
                <div className="rounded-xl border border-slate-200 dark:border-slate-700 bg-slate-50/50 dark:bg-slate-800/20 p-3.5">
                  <label className="text-sm font-semibold text-slate-700 dark:text-slate-200 block mb-1.5">
                    OAuth Client Secret
                  </label>
                  <div className="flex items-center gap-2">
                    <input
                      type={showSecret ? 'text' : 'password'}
                      value={mcpClient.client_secret}
                      readOnly
                      className="flex-1 min-w-0 input-field font-mono text-sm bg-white dark:bg-slate-900"
                      spellCheck={false}
                    />
                    <button
                      type="button"
                      onClick={() => setShowSecret(v => !v)}
                      title={showSecret ? 'Ẩn secret' : 'Hiện secret'}
                      className="w-9 h-9 flex items-center justify-center rounded-lg shrink-0 text-slate-400 hover:text-brand-indigo hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors"
                    >
                      {showSecret ? <EyeOff size={15} /> : <Eye size={15} />}
                    </button>
                    <button
                      type="button"
                      onClick={() => copyToClipboard('client-secret', mcpClient.client_secret)}
                      title="Sao chép"
                      className={cn(
                        'w-9 h-9 flex items-center justify-center rounded-lg shrink-0 transition-colors',
                        copiedKey === 'client-secret'
                          ? 'text-success bg-success/10'
                          : 'text-slate-400 hover:text-brand-indigo hover:bg-slate-100 dark:hover:bg-slate-700',
                      )}
                    >
                      {copiedKey === 'client-secret' ? <Check size={16} /> : <Copy size={15} />}
                    </button>
                  </div>
                </div>

                <div className="flex items-start gap-2 p-3 bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700 rounded-xl">
                  <Info size={12} className="text-slate-400 shrink-0 mt-0.5" />
                  <p className="text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed">
                    Bind cứng: client_id này chỉ cấp token được cho tài khoản <strong>{form.email}</strong>. Người khác login bằng tài khoản khác qua cặp này sẽ bị MCP service từ chối. Xoay secret nếu nghi rò rỉ — client_id giữ nguyên.
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* ═══════════ Card 3 — Hướng dẫn ═══════════ */}
          <div className="glass-card p-4 sm:p-6">
            <h3 className="text-h4 font-semibold text-slate-800 dark:text-slate-100 mb-4">Cách thêm vào Claude web</h3>
            <ol className="space-y-3">
              {[
                'Mở Claude web → Settings → Connectors → "Add custom connector".',
                'Dán "MCP Endpoint URL" ở Card 1 vào ô URL chính.',
                'Mở mục Advanced của dialog.',
                'Dán "OAuth Client ID" + "OAuth Client Secret" của bạn vào 2 ô tương ứng.',
                'Xác nhận → Claude mở trang đăng nhập Medinet → đăng nhập bằng đúng tài khoản này.',
                'Cho phép quyền truy cập — connector kết nối thành công.',
              ].map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="w-6 h-6 rounded-full bg-brand-indigo/10 text-brand-indigo text-xs font-bold flex items-center justify-center shrink-0">
                    {i + 1}
                  </span>
                  <span className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed">{step}</span>
                </li>
              ))}
            </ol>
          </div>
        </motion.div>
      )}
    </div>
  );
}
