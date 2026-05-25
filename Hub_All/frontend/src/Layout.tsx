import React, { useState, useEffect } from 'react';
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
  Search as SearchIcon,
  BookOpen,
  Settings as SettingsIcon,
  Sun,
  Moon
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

  // Filter logic — D-V3.1-Phase3-A LOCKED hardcode 'central' slug + Plan 02-02 backend filter authoritative
  const visibleHubs = currentRole === 'admin'
    ? hubs
    : hubs.filter((h) => h.code !== 'central' && userHubIds.includes(h.id));

  if (isLoading || hubsLoading) {
    return (
      <div
        className="px-3 py-2 border-b border-slate-200/50 dark:border-slate-700/50"
        aria-busy="true"
        aria-label="Đang tải danh sách hub"
      >
        <div className="h-8 w-full rounded-md bg-slate-200 dark:bg-slate-800 animate-pulse" />
      </div>
    );
  }

  if (visibleHubs.length === 0) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="px-3 py-2 border-b border-slate-200/50 dark:border-slate-700/50 text-xs text-slate-500 italic"
      >
        Bạn chưa được gán hub nào — liên hệ admin.
      </div>
    );
  }

  return (
    <div className="px-3 py-2 border-b border-slate-200/50 dark:border-slate-700/50">
      <label htmlFor="hub-switcher" className="sr-only">
        Hub đang xem
      </label>
      <div className="relative">
        <Database
          size={14}
          className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none"
          aria-hidden="true"
        />
        <select
          id="hub-switcher"
          value={CURRENT_HUB}
          onChange={(e) => { window.location.href = `/${e.target.value}/`; }}
          aria-label="Chọn hub đang xem"
          className="w-full rounded-md border border-slate-200 dark:border-slate-700 bg-white dark:bg-slate-900 pl-8 pr-2 py-1.5 text-sm font-medium text-slate-700 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-accent focus:border-accent"
        >
          {visibleHubs.map((h) => (
            <option key={h.code} value={h.code}>
              {h.name}
            </option>
          ))}
        </select>
      </div>
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
  return (
    <Link
      to={to}
      className={cn(
        "flex items-center gap-2.5 px-2.5 py-2.5 rounded-nav transition-all duration-300 group relative",
        active
          ? "bg-brand-indigo text-white"
          : "text-slate-500 hover:bg-white hover:shadow-sm hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-700 dark:hover:text-white"
      )}
    >
      <Icon size={20} className={cn("shrink-0", active ? "text-white" : "text-slate-400 group-hover:text-slate-600 dark:text-slate-500 dark:group-hover:text-slate-300")} />
      {!collapsed && <span className="font-medium text-sm truncate">{label}</span>}
      {badge && !collapsed && (
        <span className="ml-auto bg-danger text-white text-[10px] font-bold px-1.5 py-0.5 rounded-full min-w-[18px] text-center border-2 border-white dark:border-slate-900">
          {badge}
        </span>
      )}
      {badge && collapsed && (
        <span className="absolute top-1 right-1 bg-danger w-2 h-2 rounded-full border border-white dark:border-slate-900" />
      )}
      {collapsed && (
        <div className="absolute left-full ml-2 px-2 py-1 bg-slate-900 text-white text-xs rounded opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all whitespace-nowrap z-50 dark:bg-slate-700">
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
    { to: '/registry', icon: Database, label: 'Hub Registry', rootOnly: true },
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
    if (path === '/registry') return 'Hub Registry';
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
      className="flex h-screen bg-slate-50 dark:bg-slate-950 overflow-hidden relative"
      style={{ ['--hub-theme' as string]: HUB_BRANDING.themeColor } as React.CSSProperties}
    >
      {/* Phase 5 PROXY-04 — outermost wrapper inject CSS var --hub-theme (UI-SPEC §8.2) */}
      {/* Mobile Overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            onClick={() => setIsMobileMenuOpen(false)}
            className="fixed inset-0 bg-slate-900/40 dark:bg-black/60 z-40 lg:hidden"
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <motion.aside
        initial={false}
        animate={{
          width: collapsed ? 80 : 256,
          x: isMobileMenuOpen ? 0 : (isMobile ? -256 : 0)
        }}
        transition={{ type: 'spring', damping: 25, stiffness: 200 }}
        className={cn(
          "glass border-r border-slate-200/50 dark:border-slate-700/50 flex flex-col z-50 fixed inset-y-0 left-0 lg:relative lg:translate-x-0",
          !collapsed && "w-64 overflow-hidden",
          collapsed && "w-20 overflow-visible"
        )}
      >
        <div className="h-16 flex items-center px-6 border-b border-slate-200/50 dark:border-slate-700/50">
          {(!collapsed || isMobileMenuOpen) && (
            <motion.div
              initial={{ opacity: 0, x: -10 }}
              animate={{ opacity: 1, x: 0 }}
              className="flex items-center gap-2"
            >
              {/* Phase 5 PROXY-04 — sidebar header logo + title từ HUB_BRANDING (D-V3-Phase5-D2 LOCKED) */}
              <div
                className="w-8 h-8 rounded-xl flex items-center justify-center shadow-lg shrink-0"
                style={{ backgroundColor: HUB_BRANDING.themeColor }}
              >
                <img
                  src={HUB_BRANDING.logo}
                  alt={HUB_BRANDING.title}
                  className="w-5 h-5 object-contain"
                  style={{ filter: HUB_CONTRAST === 'slate-900' ? 'invert(1)' : 'none' }}
                  onError={(e) => {
                    (e.currentTarget as HTMLImageElement).style.display = 'none';
                    const fallback = (e.currentTarget as HTMLImageElement).nextElementSibling as HTMLElement | null;
                    if (fallback) fallback.style.display = 'block';
                  }}
                />
                <Database
                  size={18}
                  className="hidden"
                  style={{ color: HUB_CONTRAST === 'slate-900' ? '#0f172a' : 'white' }}
                />
              </div>
              <span className="font-bold text-slate-900 dark:text-white tracking-tight text-lg truncate max-w-[160px]">
                {HUB_BRANDING.title}
              </span>
            </motion.div>
          )}
          <button
            onClick={() => setCollapsed(!collapsed)}
            className={cn(
              "p-1.5 rounded-lg hover:bg-white hover:shadow-sm text-slate-400 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-all duration-300 hidden lg:flex",
              collapsed ? "mx-auto" : "ml-auto"
            )}
          >
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
          </button>
          <button
            onClick={() => setIsMobileMenuOpen(false)}
            className="p-1.5 rounded-lg hover:bg-white hover:shadow-sm text-slate-400 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-300 transition-all duration-300 lg:hidden ml-auto"
          >
            <X size={18} />
          </button>
        </div>

        {/* Plan 03-03 v3.1 Phase 3 FE-02 — Hub switcher sidebar (hide khi sidebar collapsed desktop) */}
        {(!collapsed || isMobileMenuOpen) && <HubSwitcher />}

        <nav className={cn("flex-1 p-4 space-y-1", collapsed ? "overflow-visible" : "overflow-y-auto")}>
          {menuItems.map((item, idx) => {
            if (item.type === 'group') {
              return (
                <div key={idx} className="pt-5 pb-1.5 first:pt-0">
                  {!collapsed ? (
                    <span className="px-2.5 text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                      {item.groupLabel}
                    </span>
                  ) : (
                    <div className="mx-auto w-6 border-t border-slate-200/50 dark:border-slate-700/50" />
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

        <div className="p-4 border-t border-slate-200/50 dark:border-slate-700/50">
          <div className={cn("flex items-center gap-3", collapsed ? "justify-center" : "")}>
            <Link
              to="/profile"
              className="w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-600 dark:text-slate-300 font-bold text-xs hover:ring-2 transition-all cursor-pointer shrink-0"
              title="Thông tin cá nhân"
              style={{ ['--tw-ring-color' as string]: `color-mix(in srgb, ${HUB_BRANDING.themeColor} 30%, transparent)` } as React.CSSProperties}
            >
              {user?.user.name?.charAt(0).toUpperCase() || 'U'}
            </Link>
            {!collapsed && (
              <Link to="/profile" className="flex-1 min-w-0 hover:opacity-80 transition-opacity">
                <p className="text-sm font-semibold text-slate-900 dark:text-white truncate">{user?.user.name || 'User'}</p>
                <p className="text-[10px] text-slate-500 dark:text-slate-400 truncate">{user?.user.email || ''}</p>
              </Link>
            )}
            {!collapsed && (
              <button
                onClick={async () => { await logout(); navigate('/login'); }}
                className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-danger transition-colors"
              >
                <LogOut size={16} />
              </button>
            )}
          </div>
        </div>
      </motion.aside>

      {/* Main Content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-16 glass border-b border-slate-200/50 dark:border-slate-700/50 flex items-center px-4 lg:px-6 shrink-0 z-30 sticky top-0">
          <button
            onClick={() => setIsMobileMenuOpen(true)}
            className="p-2 mr-2 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 lg:hidden"
          >
            <Menu size={20} />
          </button>

          <div className="flex flex-col">
            <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500 hidden sm:block">Hệ thống</span>
            <span className="text-xs sm:text-sm font-bold text-slate-800 dark:text-white truncate max-w-[150px] sm:max-w-none">
              {getBreadcrumb()}
            </span>
          </div>

          <div className="ml-auto flex items-center gap-3">
            <div className="relative hidden lg:block">
              <SearchIcon className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={16} />
              <input
                type="text"
                placeholder="Tìm nhanh (Cmd + K)..."
                className="bg-slate-100/80 dark:bg-slate-800 border border-transparent dark:border-slate-700 rounded-full pl-9 pr-4 py-2 text-xs w-52 xl:w-64 focus:w-72 xl:focus:w-80 focus:bg-white dark:focus:bg-slate-700 focus:border-accent/20 focus:ring-4 focus:ring-accent/5 transition-all outline-none dark:text-slate-200 dark:placeholder:text-slate-500"
              />
            </div>

            {/* Theme Toggle */}
            <button
              onClick={toggleTheme}
              className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 transition-colors"
              title={theme === 'light' ? 'Chế độ tối' : 'Chế độ sáng'}
            >
              {theme === 'light' ? <Moon size={18} /> : <Sun size={18} />}
            </button>

            <div className="relative">
              <button
                onClick={() => setNotificationsOpen(!notificationsOpen)}
                className="p-2 rounded-full hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-500 dark:text-slate-400 relative transition-colors"
              >
                <Bell size={20} />
                <span className="absolute top-1.5 right-1.5 bg-danger w-2 h-2 rounded-full border-2 border-white dark:border-slate-900" />
              </button>

              <AnimatePresence>
                {notificationsOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setNotificationsOpen(false)} />
                    <motion.div
                      initial={{ opacity: 0, scale: 0.95, y: -10 }}
                      animate={{ opacity: 1, scale: 1, y: 0 }}
                      exit={{ opacity: 0, scale: 0.95, y: -10 }}
                      className="absolute right-0 mt-2 w-[calc(100vw-2rem)] sm:w-80 glass-card z-50 overflow-hidden"
                    >
                      <div className="p-4 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                        <span className="font-bold text-sm text-slate-900 dark:text-white">Thông báo</span>
                        <button className="text-xs text-accent hover:underline">
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
                            "p-4 border-b border-slate-100 dark:border-slate-700/50 hover:bg-slate-50 dark:hover:bg-slate-700/50 cursor-pointer transition-colors",
                            n.unread && "bg-blue-50/30 dark:bg-blue-900/10"
                          )}>
                            <p className={cn("text-xs font-semibold", n.unread ? "text-slate-900 dark:text-white" : "text-slate-600 dark:text-slate-400")}>{n.title}</p>
                            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">{n.desc}</p>
                            <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-1">{n.time}</p>
                          </div>
                        ))}
                      </div>
                    </motion.div>
                  </>
                )}
              </AnimatePresence>
            </div>

            <Link to="/profile" className="flex items-center gap-2 pl-3 border-l border-slate-200/50 dark:border-slate-700/50 hover:opacity-80 transition-opacity">
              <span className="text-xs font-semibold text-slate-700 dark:text-slate-300 hidden sm:block">{user?.user.name || 'User'}</span>
              <div className="w-8 h-8 rounded-full bg-accent text-white flex items-center justify-center text-xs font-bold">
                {user?.user.name?.charAt(0).toUpperCase() || 'U'}
              </div>
            </Link>
          </div>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-y-auto p-4 lg:p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default Layout;
