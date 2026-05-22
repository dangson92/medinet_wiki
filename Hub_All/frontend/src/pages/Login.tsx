// Phase 5 PROXY-02 + PROXY-04 — Login.tsx 4 UX state machine (A/B/C/D) + branding render
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §2 (state machine)
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-CONTEXT.md §"Decisions C1 + B4 + D2"
//         .planning/phases/05-reverse-proxy-frontend-subpath/05-VALIDATION.md task 5-04-01 (T-5-04 mitigation)
//
// T-5-04 mitigation (open redirect): URL ?return= param phải qua 4-layer validation
// (strip leading slash → reject //, :// → regex hub format → KNOWN_HUBS allowlist check).
// Invalid → silent fallback central + dev console.warn.

import React, { useState, useEffect, useMemo } from 'react';
import {
  Mail, Lock, Eye, EyeOff, Loader2, AlertTriangle, ArrowRight,
  Layers, Users, ShieldCheck, FileText, Search,
} from 'lucide-react';
import { motion } from 'motion/react';
import { useAuth } from '../contexts/AuthContext';
import { useSearchParams } from 'react-router-dom';
import { CURRENT_HUB, APP_BASE } from '../services/api';
import { getBranding, getContrastTextColor, type BrandingConfig } from '../branding';

type LoginState = 'default' | 'loading' | 'error' | 'locked';

// APP_BASE export referenced để TypeScript KHÔNG warn unused — Task 1 retain import per plan §1A.
void APP_BASE;

const FEATURES = [
  {
    icon: Layers,
    title: 'Quản lý tập trung',
    desc: 'Lưu trữ và tổ chức thông tin khoa học',
    gradient: 'linear-gradient(135deg,#a855f7,#9333ea)',
  },
  {
    icon: Users,
    title: 'Chia sẻ dễ dàng',
    desc: 'Kết nối và cộng tác trong tổ chức',
    gradient: 'linear-gradient(135deg,#3b82f6,#2563eb)',
  },
  {
    icon: ShieldCheck,
    title: 'Bảo mật an toàn',
    desc: 'Dữ liệu được bảo vệ tuyệt đối',
    gradient: 'linear-gradient(135deg,#10b981,#059669)',
  },
];

// Lưới chấm trang trí
const dotStyle = (rgba: string) => ({
  backgroundImage: `radial-gradient(circle, ${rgba} 1.4px, transparent 1.4px)`,
  backgroundSize: '16px 16px',
});

// Logo "G" của Google — chỉ mang tính tượng trưng, KHÔNG gắn tính năng đăng nhập.
function GoogleIcon() {
  return (
    <svg viewBox="0 0 48 48" className="w-5 h-5" aria-hidden="true">
      <path fill="#FFC107" d="M43.611 20.083H42V20H24v8h11.303c-1.649 4.657-6.08 8-11.303 8c-6.627 0-12-5.373-12-12s5.373-12 12-12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4C12.955 4 4 12.955 4 24s8.955 20 20 20s20-8.955 20-20c0-1.341-.138-2.65-.389-3.917z" />
      <path fill="#FF3D00" d="M6.306 14.691l6.571 4.819C14.655 15.108 18.961 12 24 12c3.059 0 5.842 1.154 7.961 3.039l5.657-5.657C34.046 6.053 29.268 4 24 4C16.318 4 9.656 8.337 6.306 14.691z" />
      <path fill="#4CAF50" d="M24 44c5.166 0 9.86-1.977 13.409-5.192l-6.19-5.238A11.91 11.91 0 0 1 24 36c-5.202 0-9.619-3.317-11.283-7.946l-6.522 5.025C9.505 39.556 16.227 44 24 44z" />
      <path fill="#1976D2" d="M43.611 20.083H42V20H24v8h11.303a12.04 12.04 0 0 1-4.087 5.571l.003-.002l6.19 5.238C36.971 39.205 44 34 44 24c0-1.341-.138-2.65-.389-3.917z" />
    </svg>
  );
}

// Minh hoạ trang trí cột trái
function HeroIllustration() {
  return (
    <div className="relative h-[280px] w-[270px] shrink-0">
      <div className="absolute inset-8 rounded-full bg-white/10 blur-2xl" />

      {/* Tờ giấy phía sau */}
      <div className="absolute right-6 top-10 h-[190px] w-[150px] rotate-[10deg] rounded-2xl bg-white/70 shadow-[0_16px_32px_-14px_rgba(0,0,0,0.45)]" />

      {/* Thẻ tài liệu chính */}
      <div className="absolute left-5 top-14 w-[172px] -rotate-[7deg] rounded-2xl bg-white p-4 shadow-[0_24px_46px_-12px_rgba(0,0,0,0.5)]">
        <div className="mb-3 flex items-center gap-1.5">
          <div
            className="flex h-7 w-7 items-center justify-center rounded-lg"
            style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
          >
            <FileText size={14} className="text-white" />
          </div>
          <div className="flex-1" />
          <div className="h-1.5 w-1.5 rounded-full bg-slate-200" />
          <div className="h-1.5 w-1.5 rounded-full bg-slate-200" />
        </div>
        <div className="space-y-2">
          <div className="h-2 w-full rounded-full bg-slate-200" />
          <div className="h-2 w-4/5 rounded-full bg-slate-200" />
          <div className="h-2 w-3/5 rounded-full bg-indigo-300" />
          <div className="h-2 w-full rounded-full bg-slate-200" />
          <div className="h-2 w-2/3 rounded-full bg-slate-200" />
        </div>
      </div>

      {/* Ô tìm kiếm nổi */}
      <div className="absolute left-0 top-3 flex -rotate-[5deg] items-center gap-2 rounded-xl bg-white px-3 py-2.5 shadow-[0_16px_30px_-12px_rgba(0,0,0,0.45)]">
        <Search size={15} className="text-indigo-600" />
        <div className="h-1.5 w-14 rounded-full bg-slate-200" />
      </div>

      {/* Huy hiệu bảo mật nổi */}
      <div
        className="absolute bottom-5 right-2 flex h-16 w-16 rotate-[8deg] items-center justify-center rounded-2xl shadow-[0_16px_32px_-8px_rgba(79,70,229,0.7)]"
        style={{ background: 'linear-gradient(135deg,#6366f1,#4f46e5)' }}
      >
        <ShieldCheck size={30} className="text-white" />
      </div>
    </div>
  );
}

const LoginPage = () => {
  const [state, setState] = useState<LoginState>('default');
  const [showPassword, setShowPassword] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [countdown, setCountdown] = useState(0);

  const { login, isAuthenticated } = useAuth();
  const [searchParams] = useSearchParams();

  // ─── T-5-04 mitigation — validate ?return param strict (4-layer) ───
  const returnHub = useMemo<string | null>(() => {
    const raw = searchParams.get('return');
    if (!raw) return null;
    // Layer 1: Reject absolute URL injection (//evil.com, http://, https://) BEFORE strip
    if (raw.startsWith('//') || raw.includes('://')) {
      if (import.meta.env?.DEV) console.warn('[login] Absolute URL injection rejected:', raw);
      return null;
    }
    // Layer 2: Strip leading slash
    const candidate = raw.replace(/^\//, '');
    // Layer 3: Validate hub format Settings regex (Plan 02-05 FACTOR-04)
    if (!/^[a-z][a-z0-9_]{0,15}$/.test(candidate)) {
      if (import.meta.env?.DEV) console.warn('[login] Invalid hub format rejected:', candidate);
      return null;
    }
    // Layer 4: Validate ∈ KNOWN_HUBS (runtime config or fallback hardcode)
    const knownHubs: readonly string[] =
      (typeof window !== 'undefined' && window.__HUB_CONFIG__?.allowlist) ?? ['yte', 'duoc', 'hcns'];
    if (!knownHubs.includes(candidate)) {
      if (import.meta.env?.DEV) console.warn('[login] Invalid return hub param rejected:', candidate);
      return null;
    }
    return candidate;
  }, [searchParams]);

  // ─── State C: hub con direct visit → redirect tới central /login?return=/<hub> ───
  useEffect(() => {
    if (CURRENT_HUB !== 'central') {
      // W-05 fix: Use origin (not host) to inherit protocol — safer against HTTP/HTTPS mismatch in dev environment.
      // window.location.origin includes protocol (https://localhost), while window.location.host is host-only (localhost).
      const target = `${window.location.origin}/login?return=/${CURRENT_HUB}`;
      window.location.replace(target);
    }
  }, []);

  // ─── Branding resolution per state machine UI-SPEC §2 ───
  // State C (hub con) → render skeleton với theme của hub đang ở (CURRENT_HUB)
  // State A/B/D (central) → branding(returnHub || 'central') — fallback central nếu returnHub invalid
  const branding: BrandingConfig = useMemo(() => {
    if (CURRENT_HUB !== 'central') {
      return getBranding(CURRENT_HUB);
    }
    return getBranding(returnHub || 'central');
  }, [returnHub]);

  const contrastText = getContrastTextColor(branding.themeColor);

  // ─── M2 carry forward: post-auth navigate redirect ───
  useEffect(() => {
    if (isAuthenticated) {
      // Cross-prefix redirect — window.location reset basename + module-level api.ts re-compute
      const dest = returnHub ? `/${returnHub}/dashboard` : '/';
      window.location.replace(dest);
    }
  }, [isAuthenticated, returnHub]);

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
      // Cross-prefix redirect — window.location reset basename + module-level api.ts re-compute
      // (KHÔNG dùng react-router navigate — basename scope hiện tại)
      const dest = returnHub ? `/${returnHub}/dashboard` : '/';
      window.location.replace(dest);
      return;
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

  const isError = state === 'error';
  const isLoading = state === 'loading';
  const isLocked = state === 'locked';
  const disabled = isLoading || isLocked;
  const inputStateClass = `${isError ? 'border-danger bg-danger/[0.06]' : ''} ${
    disabled ? 'opacity-60 cursor-not-allowed' : ''
  }`;

  // ─── State C early return — skeleton trước khi redirect resolve (UI-SPEC §2.3) ───
  if (CURRENT_HUB !== 'central') {
    return (
      <div
        className="min-h-screen flex flex-col items-center justify-center"
        style={{
          ['--hub-theme' as string]: branding.themeColor,
          background: `linear-gradient(135deg, ${branding.themeColor}, color-mix(in srgb, ${branding.themeColor} 60%, black))`,
        } as React.CSSProperties}
      >
        <div className="animate-spin rounded-full h-10 w-10 border-4 border-white border-t-transparent" />
        <p className="mt-4 text-sm font-medium text-white/80">Đang chuyển đến trang đăng nhập trung tâm...</p>
      </div>
    );
  }

  return (
    <div
      className="relative flex min-h-screen overflow-x-hidden font-sans"
      style={{
        ['--hub-theme' as string]: branding.themeColor,
        background: `linear-gradient(135deg, var(--hub-theme) 0%, color-mix(in srgb, var(--hub-theme) 80%, black) 52%, color-mix(in srgb, var(--hub-theme) 60%, black) 100%)`,
      } as React.CSSProperties}
    >
      {/* Khối mờ trang trí nền */}
      <div className="pointer-events-none absolute -top-24 -left-24 h-80 w-80 rounded-full bg-white/20 blur-3xl" />
      <div className="pointer-events-none absolute top-1/3 -left-10 h-72 w-72 rounded-full bg-white/15 blur-3xl" />
      <div className="pointer-events-none absolute bottom-0 left-1/3 h-96 w-96 rounded-full bg-white/15 blur-3xl" />

      {/* ============ CỘT TRÁI — Thương hiệu ============ */}
      <div className="relative hidden flex-1 flex-col lg:flex">
        {/* Lưới chấm trang trí */}
        <div className="pointer-events-none absolute right-10 top-12 h-28 w-32 opacity-40" style={dotStyle('rgba(255,255,255,0.55)')} />
        <div className="pointer-events-none absolute bottom-20 right-24 h-24 w-28 opacity-25" style={dotStyle('rgba(255,255,255,0.55)')} />

        <div className="relative z-10 mx-auto flex h-full w-full max-w-[660px] flex-col justify-between px-8 py-12 text-white xl:py-14">
          {/* Logo — UI-SPEC §1.2 top-left logo + title + tagline branding */}
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 items-center justify-center rounded-[14px] bg-white shadow-lg">
              <img
                src={branding.logo}
                alt={branding.title}
                className="w-7 h-7 object-contain"
                onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
              />
            </div>
            <div>
              <h1 className="text-lg font-bold leading-tight tracking-tight">{branding.title}</h1>
              <p className="text-[12px] text-white/60">{branding.tagline}</p>
            </div>
          </div>

          {/* Nội dung giữa */}
          <div className="flex flex-col justify-center py-8">
            <h2 className="text-[38px] font-bold leading-[1.15] tracking-tight xl:text-[44px]">
              Kết nối tri thức,
              <br />
              <span className="text-white/45">lan tỏa giá trị.</span>
            </h2>

            <div className="mt-6 h-1 w-14 rounded-full bg-white/30" />

            <p className="mt-6 max-w-[360px] text-[15px] leading-relaxed text-white/70">
              Medinet Wiki giúp bạn lưu trữ, chia sẻ và khai thác tri thức một cách hiệu quả.
            </p>

            <div className="mt-9 flex items-center gap-8">
              {/* Danh sách tính năng */}
              <div className="space-y-5">
                {FEATURES.map((f) => (
                  <div key={f.title} className="flex items-center gap-3.5">
                    <div
                      className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl shadow-lg"
                      style={{ backgroundImage: f.gradient }}
                    >
                      <f.icon size={22} className="text-white" />
                    </div>
                    <div className="whitespace-nowrap">
                      <p className="text-[15px] font-semibold text-white">{f.title}</p>
                      <p className="text-[13px] text-white/55">{f.desc}</p>
                    </div>
                  </div>
                ))}
              </div>

              {/* Minh hoạ */}
              <div className="hidden xl:block">
                <HeroIllustration />
              </div>
            </div>
          </div>

          {/* Footer */}
          <p className="text-[12px] text-white/45">© 2025 Medinet. Hệ thống nội bộ.</p>
        </div>
      </div>

      {/* ============ CỘT PHẢI — Form đăng nhập ============ */}
      {/* Panel trắng full-height, dính sát mép trên/phải/dưới; chỉ bo góc trái làm đường chia với nền xanh */}
      <div className="relative z-10 flex w-full shrink-0 items-stretch lg:w-[44%]">
        <div className="relative flex flex-1 items-center justify-center overflow-hidden bg-white shadow-[-24px_0_60px_-18px_rgba(15,15,60,0.45)] lg:rounded-l-[40px] dark:bg-slate-900">
          {/* Lưới chấm góc */}
          <div className="pointer-events-none absolute right-8 top-8 h-24 w-24" style={dotStyle('rgba(99,102,241,0.16)')} />
          <div className="pointer-events-none absolute bottom-8 left-12 h-24 w-24" style={dotStyle('rgba(99,102,241,0.16)')} />

          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: 'easeOut' }}
            className="relative z-10 w-full max-w-[440px] px-6 py-10 sm:px-10 sm:py-12"
          >
            {/* Tiêu đề */}
            <div className="mb-8 text-center">
              <div
                className="mx-auto mb-5 flex h-16 w-16 items-center justify-center rounded-2xl"
                style={{ backgroundColor: `color-mix(in srgb, var(--hub-theme) 10%, white)` }}
              >
                <img
                  src={branding.logo}
                  alt={branding.title}
                  className="w-10 h-10 object-contain"
                  onError={(e) => { (e.currentTarget as HTMLImageElement).style.display = 'none'; }}
                />
              </div>
              <h2 className="text-[26px] font-bold tracking-tight text-slate-800 dark:text-slate-100">
                Đăng nhập
              </h2>
              <p className="mt-1.5 text-sm text-slate-500 dark:text-slate-400">
                Chào mừng bạn trở lại {branding.title}
              </p>
              {/* State B chip — chỉ render khi returnHub valid (UI-SPEC §2.2) */}
              {returnHub && (
                <div
                  className="mx-auto mt-3 inline-flex items-center gap-2 px-3 py-1.5 rounded-full text-xs font-medium"
                  style={{
                    backgroundColor: `color-mix(in srgb, var(--hub-theme) 12%, white)`,
                    color: 'var(--hub-theme)',
                  }}
                >
                  <span>Sau đăng nhập sẽ vào {branding.title}</span>
                </div>
              )}
            </div>

            <form className="space-y-5" onSubmit={handleSubmit}>
              {/* Email */}
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Email</label>
                <div className="relative">
                  <Mail className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => { setEmail(e.target.value); if (isError) setState('default'); }}
                    disabled={disabled}
                    placeholder="Nhập email của bạn"
                    className={`input-field h-12 w-full pl-11 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 ${inputStateClass}`}
                  />
                </div>
              </div>

              {/* Mật khẩu */}
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-700 dark:text-slate-200">Mật khẩu</label>
                <div className="relative">
                  <Lock className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
                  <input
                    type={showPassword ? 'text' : 'password'}
                    value={password}
                    onChange={(e) => { setPassword(e.target.value); if (isError) setState('default'); }}
                    disabled={disabled}
                    placeholder="Nhập mật khẩu"
                    className={`input-field h-12 w-full pl-11 pr-11 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 ${inputStateClass}`}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                    className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 transition-colors hover:text-slate-600 dark:hover:text-slate-300"
                  >
                    {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
                  </button>
                </div>
              </div>

              {/* Thông báo lỗi */}
              {isError && (
                <motion.p
                  initial={{ opacity: 0, y: -4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="text-sm font-medium text-danger"
                >
                  {errorMessage || 'Email hoặc mật khẩu không đúng'}
                </motion.p>
              )}

              {/* Ghi nhớ / Quên mật khẩu — hoặc — Hộp khoá tài khoản */}
              {isLocked ? (
                <motion.div
                  initial={{ opacity: 0, y: 4 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="space-y-3 rounded-xl border border-warning/30 bg-warning/[0.08] p-4"
                >
                  <div className="flex items-center gap-2">
                    <AlertTriangle size={18} className="text-warning" />
                    <h4 className="text-sm font-semibold text-[#92400e]">Tài khoản tạm khóa</h4>
                  </div>
                  <p className="text-sm text-[#78350f]">
                    Quá nhiều lần đăng nhập thất bại. Vui lòng thử lại sau:
                  </p>
                  <div className="text-2xl font-semibold tabular-nums text-warning">{formatTime(countdown)}</div>
                </motion.div>
              ) : (
                <div className="flex items-center justify-between">
                  <label className="flex cursor-pointer select-none items-center gap-2">
                    <input type="checkbox" className="h-4 w-4 cursor-pointer rounded accent-indigo-600" />
                    <span className="text-sm text-slate-600 dark:text-slate-300">Ghi nhớ đăng nhập</span>
                  </label>
                  <button
                    type="button"
                    className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                  >
                    Quên mật khẩu?
                  </button>
                </div>
              )}

              {/* Nút đăng nhập — themeColor inline gradient (D-V3-Phase5-D2 LOCKED) */}
              <button
                type="submit"
                disabled={disabled}
                style={isLocked ? undefined : {
                  background: `linear-gradient(135deg, var(--hub-theme), color-mix(in srgb, var(--hub-theme) 85%, white))`,
                  color: contrastText === 'slate-900' ? '#0f172a' : 'white',
                  boxShadow: `0 10px 30px -8px color-mix(in srgb, var(--hub-theme) 55%, transparent)`,
                }}
                className={`flex h-12 w-full items-center justify-center gap-2 rounded-xl text-sm font-semibold transition-all ${
                  isLocked
                    ? 'cursor-not-allowed bg-slate-200 text-slate-400 dark:bg-slate-700 dark:text-slate-500'
                    : 'hover:brightness-110 active:brightness-95 disabled:opacity-70'
                }`}
              >
                {isLoading ? (
                  <>
                    <Loader2 size={18} className="animate-spin" />
                    <span>Đang đăng nhập...</span>
                  </>
                ) : (
                  <>
                    <span>Đăng nhập</span>
                    <ArrowRight size={18} />
                  </>
                )}
              </button>
            </form>

            {/* Ngăn cách */}
            <div className="my-6 flex items-center gap-4">
              <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
              <span className="text-xs text-slate-400">hoặc</span>
              <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
            </div>

            {/* Nút Google — chỉ tượng trưng, chưa gắn tính năng đăng nhập */}
            <button
              type="button"
              disabled={disabled}
              className="flex h-12 w-full items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-200 dark:hover:bg-slate-700"
            >
              <GoogleIcon />
              <span>Đăng nhập với Google</span>
            </button>

            {/* Liên hệ */}
            <p className="mt-6 text-center text-sm text-slate-500 dark:text-slate-400">
              Chưa có tài khoản?{' '}
              <button
                type="button"
                className="font-semibold text-indigo-600 hover:underline dark:text-indigo-400"
              >
                Liên hệ quản trị viên
              </button>
            </p>
          </motion.div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
