import { useState, useEffect } from 'react';
import { motion } from 'motion/react';
import { Camera, Save, RefreshCw, Eye, EyeOff, Check, Loader2, AlertCircle } from 'lucide-react';
import { cn } from '../lib/utils';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

export default function Profile() {
  const { refreshUser } = useAuth();
  const [loading, setLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');
  const [showOldPassword, setShowOldPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [activeTab, setActiveTab] = useState<'info' | 'password'>('info');

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
        <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Thông tin cá nhân</h1>
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
            <h2 className="text-lg font-bold text-slate-900 dark:text-white">{form.name}</h2>
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
    </div>
  );
}
