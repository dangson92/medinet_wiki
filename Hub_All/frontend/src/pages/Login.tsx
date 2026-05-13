import React, { useState, useEffect } from 'react';
import { Mail, Lock, Eye, EyeOff, ShieldX, Loader2, AlertTriangle } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { useAuth } from '../contexts/AuthContext';
import { useNavigate } from 'react-router-dom';

type LoginState = 'default' | 'loading' | 'error' | 'locked';

const LoginPage = () => {
  const [state, setState] = useState<LoginState>('default');
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [countdown, setCountdown] = useState(0);

  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  useEffect(() => {
    if (isAuthenticated) {
      navigate('/', { replace: true });
    }
  }, [isAuthenticated, navigate]);

  useEffect(() => {
    let timer: NodeJS.Timeout;
    if (state === 'locked' && countdown > 0) {
      timer = setInterval(() => {
        setCountdown((prev) => {
          if (prev <= 1) {
            setState('default');
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [state, countdown]);

  const formatTime = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (state === 'loading' || state === 'locked') return;
    if (!email || !password) return;

    setState('loading');
    setErrorMessage('');

    const result = await login(email, password);

    if (result.success) {
      navigate('/', { replace: true });
    } else {
      const err = result.error || 'Đăng nhập thất bại';
      setErrorMessage(err);

      if (err.toLowerCase().includes('locked') || err.toLowerCase().includes('khóa')) {
        setState('locked');
        // Try to extract countdown from error message, default to 15 minutes
        const match = err.match(/(\d+)\s*(phút|minute)/i);
        setCountdown(match ? parseInt(match[1]) * 60 : 900);
      } else {
        setState('error');
      }
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row font-sans overflow-hidden">
      {/* Left Column */}
      <div className="hidden lg:flex w-1/2 bg-brand-indigo relative items-center justify-center p-12">
        <div className="relative text-center">
          <h1 className="text-[30px] font-bold text-white tracking-[-0.02em] mb-2">Medinet Wiki</h1>
          <p className="text-base text-white/80">Hệ thống quản lý tri thức nội bộ</p>
        </div>

        <div className="absolute bottom-12 left-12 text-[12px] text-white/50">
          © 2025 Medinet. Hệ thống nội bộ.
        </div>
      </div>

      {/* Right Column */}
      <div className="flex-1 bg-slate-50 dark:bg-slate-950 flex items-center justify-center p-4 lg:p-12 relative">
        <AnimatePresence mode="wait">
          <motion.div
            key={state === 'error' ? 'error' : 'normal'}
            initial={{ opacity: 0, scale: 0.96, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            transition={{ duration: 0.15 }}
            className={`w-full max-w-[420px] ${state === 'locked' ? 'bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700' : 'glass-card'} p-6 sm:p-10 shadow-lg rounded-[20px]`}
          >
            <div className="mb-8">
              <h2 className="text-[20px] font-semibold text-slate-800 dark:text-slate-100 mb-1">Quản trị Medinet Wiki</h2>
              <p className="text-sm text-slate-500 dark:text-slate-400">Đăng nhập vào hệ thống quản trị trung tâm</p>
            </div>

            <form className="space-y-6" onSubmit={handleSubmit}>
              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-200 block">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={18} />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); if (state === 'error') setState('default'); }}
                    disabled={state === 'loading' || state === 'locked'}
                    placeholder="admin@medinet.vn"
                    className={`input-field w-full pl-11 ${
                      state === 'error' ? 'border-danger bg-danger/[0.06]' : ''
                    } ${state === 'loading' ? 'opacity-60 cursor-not-allowed' : ''} ${
                      state === 'locked' ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-slate-700 dark:text-slate-200 block">Mật khẩu</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={18} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); if (state === 'error') setState('default'); }}
                    disabled={state === 'loading' || state === 'locked'}
                    placeholder="Nhập mật khẩu"
                    className={`input-field w-full pl-11 pr-11 ${
                      state === 'error' ? 'border-danger bg-danger/[0.06]' : ''
                    } ${state === 'loading' ? 'opacity-60 cursor-not-allowed' : ''} ${
                      state === 'locked' ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 transition-colors"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {state === 'error' && (
                <motion.p
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-sm font-medium text-danger"
                >
                  {errorMessage || 'Email hoặc mật khẩu không đúng'}
                </motion.p>
              )}

              {state === 'locked' ? (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="bg-warning/[0.08] border border-warning/30 rounded-[10px] p-4 space-y-3"
                >
                  <div className="flex items-center gap-2 text-warning-800">
                    <AlertTriangle size={18} className="text-warning" />
                    <h4 className="text-sm font-semibold text-[#92400e]">Tài khoản tạm khóa</h4>
                  </div>
                  <p className="text-sm text-[#78350f]">
                    Quá nhiều lần đăng nhập thất bại. Vui lòng thử lại sau:
                  </p>
                  <div className="text-[24px] font-semibold text-warning tabular-nums">
                    {formatTime(countdown)}
                  </div>
                </motion.div>
              ) : (
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="remember"
                    className="w-4 h-4 rounded border-slate-300 dark:border-slate-600 text-brand-indigo focus:ring-brand-indigo transition-all"
                  />
                  <label htmlFor="remember" className="ml-2 text-sm text-slate-600 dark:text-slate-300 cursor-pointer select-none">
                    Ghi nhớ đăng nhập
                  </label>
                </div>
              )}

              <button
                type="submit"
                disabled={state === 'loading' || state === 'locked'}
                className={`w-full transition-all ${
                  state === 'locked'
                    ? 'bg-slate-200 dark:bg-slate-700 text-slate-400 dark:text-slate-500 text-sm cursor-not-allowed rounded-button px-4 py-2 flex items-center justify-center gap-2'
                    : state === 'loading'
                    ? 'btn-primary opacity-80 cursor-not-allowed'
                    : 'btn-primary'
                }`}
              >
                {state === 'loading' ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Đang đăng nhập...</span>
                  </>
                ) : (
                  <span>Đăng nhập</span>
                )}
              </button>
            </form>

            <div className="mt-8 text-center">
              <p className="text-[12px] text-slate-400 dark:text-slate-500">
                Chỉ dành cho quản trị viên. Tài khoản được cấp bởi hệ thống.
              </p>
            </div>
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  );
};

export default LoginPage;
