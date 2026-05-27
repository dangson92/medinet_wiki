import React, { useState, useEffect, useRef } from 'react';
import {
  LayoutDashboard,
  Search,
  Users,
  Database,
  RefreshCw,
  History,
  Key,
  Zap,
  LogOut,
  Bell,
  ChevronLeft,
  ChevronRight,
  Menu,
  X,
  BookOpen,
  Settings as SettingsIcon,
  Sun,
  Moon,
  Plus,
  ChevronDown,
  Check
} from 'lucide-react';
import { Link, useLocation, useNavigate, Outlet } from 'react-router-dom';
import { cn } from './lib/utils';
import { motion, AnimatePresence } from 'motion/react';
import { useTheme } from './contexts/ThemeContext';
import { useAuth } from './contexts/AuthContext';
import { getBranding, getContrastTextColor } from './branding';
import { api, CURRENT_HUB } from './services/api';
import type { UserRole, HubAPI } from './services/api';

// Phase 5 PROXY-04 — branding resolution module-level (compute 1 lần)
// Source: .planning/phases/05-reverse-proxy-frontend-subpath/05-UI-SPEC.md §3
const HUB_BRANDING = getBranding(CURRENT_HUB);
const HUB_CONTRAST = getContrastTextColor(HUB_BRANDING.themeColor);

// Plan 03-03 v3.1 Phase 3 FE-02 — Hub switcher sidebar component
// Source: .planning/phases/03-frontend-form-refactor/03-CONTEXT.md D-V3.1-Phase3-A LOCKED (hardcode 'central' slug)
//         .planning/phases/03-frontend-form-refactor/03-UI-SPEC.md §6.2 + §7.2 + §8.2
//         .planning/phases/03-frontend-form-refactor/03-PATTERNS.md Option A userHubIds derive (roles[].hub_id)
function HubSwitcher() {
  const { user, isLoading } = useAuth();
  const currentUser = user?.user;
  const currentRole: UserRole = (currentUser?.role as UserRole) ?? 'viewer';
  // Option A LOCKED — derive userHubIds từ roles: RoleAPI[] (existing M2/v3.0)
  const userHubIds: string[] = user?.roles?.map((r) => r.hub_id) ?? [];

  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [hubsLoading, setHubsLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let mounted = true;
    api.getHubs().then((res) => {
      if (mounted && res.success && res.data) {
        setHubs(res.data);
      }
    }).finally(() => {
      if (mounted) setHubsLoading(false);
    });
    return () => { mounted = false; };
  }, []);

  // Click outside + Escape close
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  // Filter logic — D-V3.1-Phase3-A LOCKED hardcode 'central' slug + Plan 02-02 backend filter authoritative
  const visibleHubs = currentRole === 'admin'
    ? hubs
    : hubs.filter((h) => h.code !== 'central' && userHubIds.includes(h.id));

  if (isLoading || hubsLoading) {
    return (
      <div
        className="px-4 py-3"
        aria-busy="true"
        aria-label="Đang tải danh sách hub"
      >
        <div className="h-10 w-full rounded-lg bg-surface-container-low animate-pulse" />
      </div>
    );
  }

  if (visibleHubs.length === 0) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="px-4 py-3 text-body-sm text-on-surface-variant italic"
      >
        Bạn chưa được gán hub nào — liên hệ admin.
      </div>
    );
  }

  const currentHub = visibleHubs.find((h) => h.code === CURRENT_HUB) ?? visibleHubs[0];

  return (
    <div className="px-4 py-3 relative" ref={dropdownRef}>
      {/* Mẫu giao-dien-mau — trigger button: hub letter icon + name + chevron */}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label="Chọn hub đang xem"
        className="w-full flex items-center gap-2.5 px-3 py-2 rounded-lg border border-outline-variant bg-white text-on-surface hover:border-primary/40 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-primary/20 dark:bg-slate-800 dark:border-slate-700 dark:text-white"
      >
        <span className="w-6 h-6 rounded bg-primary/10 text-primary flex items-center justify-center font-bold text-[11px] shrink-0">
          {currentHub.name.charAt(0)}
        </span>
        <span className="flex-1 text-left text-body-sm font-bold truncate">
          {currentHub.name}
        </span>
        <ChevronDown
          size={16}
          className={cn(
            "text-on-surface-variant transition-transform shrink-0",
            open && "rotate-180"
          )}
        />
      </button>

      {/* Mẫu — open dropdown panel: selected highlighted bg-primary/10 + check icon */}
      {open && (
        <div
          role="listbox"
          aria-label="Danh sách hub"
          className="absolute left-4 right-4 top-full mt-1 z-50 bg-white rounded-lg border border-outline-variant shadow-lg overflow-hidden dark:bg-slate-800 dark:border-slate-700"
        >
          {visibleHubs.map((h) => {
            const isActive = h.code === CURRENT_HUB;
            return (
              <button
                key={h.code}
                type="button"
                role="option"
                aria-selected={isActive}
                onClick={() => {
                  setOpen(false);
                  if (!isActive) window.location.href = `/${h.code}/`;
                }}
                className={cn(
                  "w-full flex items-center gap-2.5 px-3 py-2.5 text-left text-body-sm font-medium transition-colors",
                  isActive
                    ? "bg-primary/10 text-primary dark:bg-primary/20"
                    : "text-on-surface hover:bg-surface-container-low dark:text-white dark:hover:bg-slate-700"
                )}
              >
                <span
                  className={cn(
                    "w-6 h-6 rounded flex items-center justify-center font-bold text-[11px] shrink-0",
                    isActive
                      ? "bg-primary text-on-primary"
                      : "bg-surface-container text-on-surface-variant dark:bg-slate-700 dark:text-slate-300"
                  )}
                >
                  {h.name.charAt(0)}
                </span>
                <span className="flex-1 truncate">{h.name}</span>
                {isActive && <Check size={16} className="text-primary shrink-0" />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

const SidebarItem = ({
  to,
  icon: Icon,
  label,
  badge,
  collapsed,
  active
}: {
  to: string;
  icon: React.ElementType;
  label: string;
  badge?: string;
  collapsed: boolean;
  active: boolean;
}) => {
  // Mẫu giao-dien-mau — active: bg-primary text-on-primary; hover: bg-surface-container-low
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-3 px-3 py-2.5 rounded-lg transition-colors duration-200 group relative",
        active
          ? "bg-primary text-on-primary shadow-sm"
          : "text-on-surface-variant hover:bg-surface-container-low hover:text-primary dark:text-slate-400 dark:hover:bg-slate-800 dark:hover:text-white"
      )}
    >
      <Icon
        size={20}
        className={cn(
          "shrink-0",
          active ? "text-on-primary" : "text-on-surface-variant group-hover:text-primary dark:text-slate-500 dark:group-hover:text-slate-200"
        )}
      />
      {!collapsed && <span className="font-medium text-body-sm truncate">{label}</span>}
      {badge && !collapsed && (
        <span className={cn(
          "ml-auto text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center",
          active ? "bg-white/20 text-on-primary" : "bg-error text-on-error"
        )}>
          {badge}
        </span>
      )}
      {badge && collapsed && (
        <span className="absolute top-1 right-1 bg-error w-2 h-2 rounded-full border border-white dark:border-slate-900" />
      )}
      {collapsed && (
        <div className="absolute left-full ml-2 px-2 py-1 bg-inverse-surface text-inverse-on-surface text-xs rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50">
          {label}
        </div>
      )}
    </Link>
  );
};

const Layout = () => {
  const [collapsed, setCollapsed] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const [isMobile, setIsMobile] = useState(window.innerWidth < 1024);
  const location = useLocation();
  const navigate = useNavigate();
  const { theme, toggleTheme } = useTheme();
  const { user, logout } = useAuth();

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth < 1024);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    setIsMobileMenuOpen(false);
  }, [location.pathname]);

  // Root-only menu hidden cho user không phải super-admin (role !== 'admin').
  // Reason: D-V3.1-01 LOCKED 'admin' = global super-admin; hub_admin/editor/viewer
  // KHÔNG có quyền truy cập Hub Registry, Quản lý API Key, hoặc nhóm Hệ thống
  // (Audit Log + Token Usage + Cài đặt). FE filter là defense in depth — backend
  // endpoint tương ứng đã enforce require_role("admin") (FACTOR-02 central-only mount).
  const isRoot = user?.user.role === 'admin';
  const menuItems = [
    { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
    { type: 'group', groupLabel: 'Tri thức' },
    { to: '/search', icon: Search, label: 'Hỏi đáp AI' },
    { to: '/documents', icon: BookOpen, label: 'Danh sách tri thức' },
    { to: '/sync', icon: RefreshCw, label: 'Hàng đợi Sync', badge: '3' },
    { type: 'group', groupLabel: 'Quản trị' },
    { to: '/users', icon: Users, label: 'Quản lý User' },
    { to: '/registry', icon: Database, label: 'Quản lý Hub', rootOnly: true },
    { to: '/api-keys', icon: Key, label: 'Quản lý API Key', rootOnly: true },
    { type: 'group', groupLabel: 'Hệ thống', rootOnly: true },
    { to: '/logs', icon: History, label: 'Audit Log', rootOnly: true },
    { to: '/usage', icon: Zap, label: 'Token & API Usage', rootOnly: true },
    { to: '/settings', icon: SettingsIcon, label: 'Cài đặt hệ thống', rootOnly: true },
  ].filter((item) => isRoot || !item.rootOnly);

  const getBreadcrumb = () => {
    const path = location.pathname;
    if (path === '/') return 'Dashboard';
    if (path === '/search') return 'Hỏi đáp AI';
    if (path === '/documents') return 'Danh sách tri thức';
    if (path === '/users') return 'Quản lý User';
    if (path === '/registry') return 'Quản lý Hub';
    if (path === '/sync') return 'Hàng đợi Sync';
    if (path === '/logs') return 'Audit Log';
    if (path === '/usage') return 'Token & API Usage';
    if (path === '/api-keys') return 'Quản lý API Key';
    if (path === '/settings') return 'Cài đặt hệ thống';
    if (path === '/profile') return 'Thông tin cá nhân';
    return 'Dashboard';
  };

  return (
    <div
      className="flex h-screen bg-background dark:bg-slate-950 overflow-hidden relative"
      style={{ ['--hub-theme' as string]: HUB_BRANDING.themeColor } as React.CSSProperties}
    >
      {/* Mẫu giao-dien-mau — outermost bg-background (#faf9fe) + CSS var --hub-theme */}
      {/* Mobile Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsMobileMenuOpen(false)}
            className="fixed inset-0 bg-inverse-surface/40 dark:bg-black/60 z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar — mẫu giao-dien-mau: bg-background + border-r border-outline-variant + w-260px */}
      <motion.aside
        initial={false}
        animate={{
          width: collapsed ? 80 : 260,
          x: isMobileMenuOpen ? 0 : (isMobile ? -260 : 0)
        }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className={cn(
          "bg-background border-r border-outline-variant flex flex-col z-50 fixed inset-y-0 left-0 lg:relative lg:translate-x-0 dark:bg-slate-900 dark:border-slate-700",
          !collapsed && "w-[260px] overflow-hidden",
          collapsed && "w-20 overflow-visible"
        )}
      >
        {/* Mẫu — logo block px-6 py-6 border-b border-outline-variant.
            Override padding khi wordmark logo (.png) để cho phép full-width. */}
        <div
          className={cn(
            "flex items-center gap-3 border-b border-outline-variant dark:border-slate-700",
            HUB_BRANDING.logo.endsWith('.png') && (!collapsed || isMobileMenuOpen)
              ? "pl-2 pr-2 py-0"
              : "px-6 py-5"
          )}
        >
          {(!collapsed || isMobileMenuOpen) && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className={cn(
                "flex items-center min-w-0",
                HUB_BRANDING.logo.endsWith('.png') ? "flex-1" : "gap-3"
              )}
            >
              {HUB_BRANDING.logo.endsWith('.png') ? (
                // Wordmark logo (Medinet Wiki main) — render full image only,
                // no colored container, no text (wordmark already contains brand).
                // Negative vertical margin to crop ~half of the PNG's transparent padding.
                <img
                  src={HUB_BRANDING.logo}
                  alt={HUB_BRANDING.title}
                  className="w-full h-auto max-w-none object-contain -my-2"
                />
              ) : (
                <>
                  {/* Mẫu — w-10 h-10 bg-primary rounded-lg (PROXY-04: per-hub themeColor via --hub-theme) */}
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                    style={{ backgroundColor: HUB_BRANDING.themeColor }}
                  >
                    <img
                      src={HUB_BRANDING.logo}
                      alt={HUB_BRANDING.title}
                      className="w-6 h-6 object-contain"
                      style={{ filter: HUB_CONTRAST === 'slate-900' ? 'invert(1)' : 'none' }}
                      onError={(e) => {
                        (e.currentTarget as HTMLImageElement).style.display = 'none';
                        const fallback = (e.currentTarget as HTMLImageElement).nextElementSibling as HTMLElement | null;
                        if (fallback) fallback.style.display = 'block';
                      }}
                    />
                    <Database
                      size={22}
                      className="hidden"
                      style={{ color: HUB_CONTRAST === 'slate-900' ? '#0f172a' : 'white' }}
                    />
                  </div>
                  {/* Mẫu — text-headline-md text-on-surface + text-[10px] text-on-surface-variant */}
                  <div className="flex flex-col min-w-0 leading-tight">
                    <span className="font-display font-bold text-on-surface dark:text-white text-[18px] truncate max-w-[160px] leading-tight">
                      {HUB_BRANDING.title}
                    </span>
                    <span className="text-[10px] text-on-surface-variant dark:text-slate-400 truncate max-w-[160px] mt-0.5">
                      Hệ thống quản lý tri thức
                    </span>
                  </div>
                </>
              )}
            </motion.div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn(
              "p-1.5 rounded-lg hover:bg-surface-container-low text-on-surface-variant hover:text-primary transition-colors hidden lg:flex dark:hover:bg-slate-800 dark:hover:text-white",
              collapsed ? "mx-auto" : "ml-auto"
            )}
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            className="p-1.5 rounded-lg hover:bg-surface-container-low text-on-surface-variant hover:text-primary transition-colors lg:hidden ml-auto dark:hover:bg-slate-800"
          >
            <X size={18} />
          </button>
        </div>

        {/* Plan 03-03 v3.1 Phase 3 FE-02 — Hub switcher sidebar (hide khi sidebar collapsed desktop) */}
        {(!collapsed || isMobileMenuOpen) && <HubSwitcher />}

        <nav className={cn("flex-1 px-3 py-2 space-y-1", collapsed ? "overflow-visible" : "overflow-y-auto")}>
          {menuItems.map((item, idx) => {
            if (item.type === 'group') {
              // Mẫu — pt-4 pb-2 px-3 text-[10px] font-bold text-outline uppercase tracking-wider
              return (
                <div key={idx} className="pt-4 pb-2 first:pt-2">
                  {!collapsed ? (
                    <span className="px-3 text-[10px] font-bold uppercase tracking-wider text-outline dark:text-slate-500">
                      {item.groupLabel}
                    </span>
                  ) : (
                    <div className="mx-auto w-6 border-t border-outline-variant dark:border-slate-700" />
                  )}
                </div>
              );
            }
            return (
              <SidebarItem
                key={item.to}
                to={item.to!}
                icon={item.icon!}
                label={item.label!}
                badge={item.badge}
                collapsed={collapsed}
                active={location.pathname === item.to}
              />
            );
          })}
        </nav>

        {/* Mẫu — footer profile: border-t border-outline-variant + avatar bg-secondary-fixed */}
        <div className="p-3 border-t border-outline-variant dark:border-slate-700">
          <div className={cn("flex items-center gap-3 px-3 py-2 rounded-lg hover:bg-surface-container-low dark:hover:bg-slate-800 transition-colors", collapsed && "justify-center")}>
            <Link
              to="/profile"
              className="w-8 h-8 rounded-full bg-secondary-fixed text-on-secondary-fixed flex items-center justify-center font-bold text-body-sm shrink-0 dark:bg-slate-700 dark:text-slate-200"
              title="Thông tin cá nhân"
            >
              {user?.user.name?.charAt(0).toUpperCase() || 'U'}
            </Link>
            {!collapsed && (
              <>
                <Link to="/profile" className="flex-1 min-w-0 hover:opacity-80 transition-opacity">
                  <p className="text-body-sm font-bold text-on-surface dark:text-white truncate">{user?.user.name || 'User'}</p>
                  <p className="text-[10px] text-on-surface-variant dark:text-slate-400 truncate">{user?.user.email || ''}</p>
                </Link>
                <button
                  onClick={async () => { await logout(); navigate('/login'); }}
                  className="text-outline hover:text-error transition-colors"
                  title="Đăng xuất"
                >
                  <LogOut size={18} />
                </button>
              </>
            )}
          </div>
        </div>
      </motion.aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mẫu giao-dien-mau — header bg-background/80 backdrop-blur-md border-b border-transparent */}
        <header className="h-16 bg-background/80 dark:bg-slate-900/80 backdrop-blur-md flex items-center px-4 lg:px-8 shrink-0 z-30 sticky top-0">
          <button
            onClick={() => setIsMobileMenuOpen(true)}
            className="p-2 mr-2 rounded-lg hover:bg-surface-container-low text-on-surface-variant lg:hidden dark:hover:bg-slate-800"
          >
            <Menu size={20} />
          </button>

          {/* Mobile: breadcrumb fallback */}
          <div className="flex flex-col lg:hidden">
            <span className="text-[10px] font-medium text-on-surface-variant">Hệ thống</span>
            <span className="text-body-sm font-bold text-on-surface dark:text-white truncate max-w-[150px]">
              {getBreadcrumb()}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-4 lg:gap-6">
            <div className="flex items-center gap-1 lg:gap-2">
              {/* Theme Toggle */}
              <button
                onClick={toggleTheme}
                className="p-2 text-on-surface-variant hover:text-primary transition-colors"
                title={theme === 'light' ? 'Chế độ tối' : 'Chế độ sáng'}
              >
                {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
              </button>

              <div className="relative">
                <button
                  onClick={() => setNotificationsOpen(!notificationsOpen)}
                  className="p-2 text-on-surface-variant hover:text-primary relative transition-colors"
                >
                  <Bell size={20} />
                  <span className="absolute top-2 right-2 bg-error w-2 h-2 rounded-full border border-background dark:border-slate-900" />
                </button>

              <AnimatePresence>
                {notificationsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setNotificationsOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95, y: -10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: -10 }}
                      className="absolute right-0 mt-2 w-[calc(100vw-2rem)] sm:w-80 m3-card z-50 overflow-hidden"
                    >
                      <div className="p-4 border-b border-outline-variant flex justify-between items-center">
                        <span className="font-bold text-body-sm text-on-surface dark:text-white">Thông báo</span>
                        <button className="text-[11px] text-primary font-bold hover:underline">
                          Đánh dấu đã đọc
                        </button>
                      </div>
                      <div className="max-h-96 overflow-y-auto">
                        {[
                          { title: 'Sync mới từ Hub Tâm Đạo', desc: '8 trang đang chờ duyệt', time: '30 phút trước', unread: true },
                          { title: 'User mới đăng nhập', desc: 'Nguyễn Văn A đã đăng nhập Hub HCNS lần đầu', time: '2 giờ trước', unread: true },
                          { title: 'API Key sắp hết hạn', desc: 'Key "Claude Desktop" sẽ hết hạn trong 7 ngày', time: '1 ngày trước', unread: false },
                        ].map((n, i) => (
                          <div key={i} className={cn(
                            "p-4 border-b border-outline-variant/40 hover:bg-surface-container-low cursor-pointer transition-colors dark:hover:bg-slate-700/50",
                            n.unread && "bg-primary/[0.03] dark:bg-primary/10"
                          )}>
                            <p className={cn("text-body-sm font-semibold", n.unread ? "text-on-surface dark:text-white" : "text-on-surface-variant")}>{n.title}</p>
                            <p className="text-[11px] text-on-surface-variant mt-0.5">{n.desc}</p>
                            <p className="text-[10px] text-outline mt-1">{n.time}</p>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
              </div>
            </div>

            {/* Mẫu giao-dien-mau — CTA "Nạp tri thức mới" bg-primary rounded-lg → /documents/new upload page */}
            <Link
              to="/documents/new"
              className="hidden sm:inline-flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-sm hover:bg-primary-container transition-all shadow-sm"
              title="Nạp tri thức mới"
            >
              <Plus size={16} strokeWidth={2.5} />
              <span className="hidden md:inline">Nạp tri thức mới</span>
            </Link>

            {/* Mẫu — user chip: name + avatar bg-secondary border-l pl-6 */}
            <Link to="/profile" className="flex items-center gap-3 border-l border-outline-variant pl-4 lg:pl-6 hover:opacity-80 transition-opacity dark:border-slate-700">
              <span className="text-body-sm font-semibold text-on-surface dark:text-white hidden sm:block">{user?.user.name || 'User'}</span>
              <div className="w-8 h-8 rounded-full bg-secondary text-on-secondary flex items-center justify-center font-bold text-xs shadow-sm">
                {user?.user.name?.charAt(0).toUpperCase() || 'U'}
              </div>
            </Link>
          </div>
        </header>

        {/* Content — full-width sát sidebar, KHÔNG max-width center */}
        <main className="flex-1 overflow-y-auto relative bg-background dark:bg-slate-950">
          <div className="p-4 lg:p-6 min-h-[calc(100%-3rem)]">
            <Outlet />
          </div>
          {/* Mẫu giao-dien-mau — footer copyright */}
          <footer className="px-6 py-4 text-center text-[11px] text-on-surface-variant border-t border-outline-variant dark:border-slate-700">
            © {new Date().getFullYear()} MEDINET GROUP — KNOWLEDGE BASE MANAGEMENT SYSTEM
          </footer>
        </main>
      </div>

      {/* Mẫu giao-dien-mau — status chip floating bottom-right */}
      <div
        role="status"
        aria-live="polite"
        className="fixed bottom-4 right-4 z-40 inline-flex items-center gap-2 rounded-full bg-white/95 dark:bg-slate-800/95 backdrop-blur px-3.5 py-1.5 text-[11px] font-semibold text-on-surface-variant shadow-md ring-1 ring-outline-variant dark:ring-slate-700"
        title="Trạng thái hệ thống — đang hoạt động"
      >
        <span className="w-2 h-2 rounded-full bg-emerald-500" />
        <span>Trạng thái hệ thống</span>
      </div>
    </div>
  );
};

export default Layout;
