import React, { useState, useMemo, useEffect, useCallback } from 'react';
import { api, HubAPI, UserWithRolesAPI } from '../services/api';
import { User } from '../types';
import { cn } from '../lib/utils';
import { Search, Plus, Shield, UserX, UserCheck, Mail, X, CheckCircle2, MoreVertical, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Pagination from '../components/Pagination';

const UserManagement = () => {
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [activeTab, setActiveTab] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [roleFilter, setRoleFilter] = useState('all');
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isDisableDialogOpen, setIsDisableDialogOpen] = useState(false);
  const [isEditRoleModalOpen, setIsEditRoleModalOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<any>(null);
  const [newRole, setNewRole] = useState<'admin' | 'viewer'>('viewer');
  const [actionMenuId, setActionMenuId] = useState<string | null>(null);
  const [currentPage, setCurrentPage] = useState(1);
  const itemsPerPage = 10;

  const [users, setUsers] = useState<User[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(false);
  const [actionLoading, setActionLoading] = useState(false);

  // Add modal form state
  const [newUserName, setNewUserName] = useState('');
  const [newUserEmail, setNewUserEmail] = useState('');
  const [newUserRole, setNewUserRole] = useState<'admin' | 'viewer'>('viewer');

  const activeHub = hubs.find(h => h.id === activeTab);

  // Fetch hubs on mount
  useEffect(() => {
    const fetchHubs = async () => {
      try {
        const res = await api.getHubs();
        if (res.success && res.data) {
          const activeHubs = res.data.filter(h => h.status === 'active');
          setHubs(res.data);
          if (activeHubs.length > 0 && !activeTab) {
            setActiveTab(activeHubs[0].id);
          }
        }
      } catch (err) {
        console.error('Failed to fetch hubs:', err);
      }
    };
    fetchHubs();
  }, []);

  // Map API user to FE User type
  const mapUser = useCallback((item: UserWithRolesAPI, hubId: string): User => {
    const matchingRole = item.roles.find(r => r.hub_id === hubId);
    return {
      id: item.user.id,
      name: item.user.name,
      email: item.user.email,
      role: (matchingRole?.role === 'admin' ? 'admin' : 'viewer') as 'admin' | 'viewer',
      hubId: hubId,
      createdAt: new Date(item.user.created_at).toLocaleDateString('vi-VN'),
      lastLogin: item.user.updated_at ? new Date(item.user.updated_at).toLocaleDateString('vi-VN') : 'Chưa đăng nhập',
      status: item.user.status as 'active' | 'disabled',
    };
  }, []);

  // Fetch users when tab/search/filter/page changes
  const fetchUsers = useCallback(async () => {
    if (!activeTab) return;
    setLoading(true);
    try {
      const params: any = {
        hub_id: activeTab,
        page: currentPage,
        per_page: itemsPerPage,
      };
      if (searchQuery) params.search = searchQuery;
      if (roleFilter !== 'all') params.role = roleFilter;

      const res = await api.getUsers(params);
      if (res.success && res.data) {
        setUsers(res.data.map(u => mapUser(u, activeTab)));
        if (res.meta) {
          setTotalItems(res.meta.total);
          setTotalPages(res.meta.total_pages);
        } else {
          setTotalItems(res.data.length);
          setTotalPages(Math.ceil(res.data.length / itemsPerPage));
        }
      }
    } catch (err) {
      console.error('Failed to fetch users:', err);
    } finally {
      setLoading(false);
    }
  }, [activeTab, searchQuery, roleFilter, currentPage, mapUser]);

  useEffect(() => {
    fetchUsers();
  }, [fetchUsers]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  const handleRoleFilterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    setRoleFilter(e.target.value);
    setCurrentPage(1);
  };

  const handleTabChange = (hubId: string) => {
    setActiveTab(hubId);
    setCurrentPage(1);
  };

  const handleUpdateRole = async () => {
    if (!selectedUser || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.changeUserRole(selectedUser.id, activeTab, newRole);
      if (res.success) {
        setIsEditRoleModalOpen(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to update role:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleDisableUser = async () => {
    if (!selectedUser || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.changeUserStatus(selectedUser.id, 'disabled');
      if (res.success) {
        setIsDisableDialogOpen(false);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to disable user:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleEnableUser = async (user: User) => {
    if (actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.changeUserStatus(user.id, 'active');
      if (res.success) {
        setActionMenuId(null);
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to enable user:', err);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCreateUser = async () => {
    if (!newUserName || !newUserEmail || actionLoading) return;
    setActionLoading(true);
    try {
      const res = await api.createUser({
        name: newUserName,
        email: newUserEmail,
        password: crypto.randomUUID(),
        hub_id: activeTab,
        role: newUserRole,
      });
      if (res.success) {
        setIsAddModalOpen(false);
        setNewUserName('');
        setNewUserEmail('');
        setNewUserRole('viewer');
        fetchUsers();
      }
    } catch (err) {
      console.error('Failed to create user:', err);
    } finally {
      setActionLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex border-b border-slate-200 dark:border-slate-700 overflow-x-auto no-scrollbar scroll-smooth">
        <div className="flex min-w-max">
          {hubs.filter(h => h.status === 'active').map((hub) => (
            <button
              key={hub.id}
              onClick={() => handleTabChange(hub.id)}
              className={cn(
                "px-4 sm:px-6 py-3 text-xs sm:text-sm font-medium transition-all relative",
                activeTab === hub.id ? "text-accent" : "text-slate-500 dark:text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
              )}
            >
              {hub.name}
              {activeTab === hub.id && (
                <motion.div
                  layoutId="activeTab"
                  className="absolute bottom-0 left-0 right-0 h-0.5 bg-accent"
                />
              )}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col lg:flex-row justify-between gap-4">
        <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3 flex-1 max-w-3xl">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={16} />
            <input
              type="text"
              placeholder="Tìm theo tên hoặc email..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="input-field w-full pl-10"
            />
          </div>
          <select
            value={roleFilter}
            onChange={handleRoleFilterChange}
            className="input-field min-w-[140px]"
          >
            <option value="all">Tất cả quyền</option>
            <option value="admin">Admin</option>
            <option value="viewer">Viewer</option>
          </select>
        </div>
        <button
          onClick={() => setIsAddModalOpen(true)}
          className="btn-primary shrink-0"
        >
          <Plus size={18} /> Thêm User
        </button>
      </div>

      <div className="glass-card">
        <div className="">
          {loading ? (
            <div className="flex items-center justify-center py-20">
              <Loader2 className="animate-spin text-accent" size={28} />
            </div>
          ) : (
          <table className="w-full text-left border-collapse min-w-[700px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tên</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Email</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Quyền</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Ngày tạo</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Đăng nhập cuối</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {users.map((user) => (
                <tr key={user.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors group">
                  <td className="px-5 py-4">
                    <span className="font-semibold text-sm text-slate-900 dark:text-white">{user.name}</span>
                  </td>
                  <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300">{user.email}</td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                      user.role === 'admin' ? "bg-slate-800 text-white" : "bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300"
                    )}>
                      {user.role}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{user.createdAt}</td>
                  <td className="px-5 py-4 text-xs text-slate-500 dark:text-slate-400">{user.lastLogin}</td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                      user.status === 'active' ? "bg-success/10 text-success" : "bg-danger/10 text-danger"
                    )}>
                      {user.status === 'active' ? 'Hoạt động' : 'Đã vô hiệu'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <div className="relative inline-flex">
                      <button
                        onClick={() => setActionMenuId(actionMenuId === user.id ? null : user.id)}
                        className={cn(
                          "p-1.5 rounded-lg transition-colors text-slate-400 dark:text-slate-500 hover:text-slate-600 dark:hover:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700",
                          actionMenuId === user.id && "text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700"
                        )}
                      >
                        <MoreVertical size={16} />
                      </button>
                      <AnimatePresence>
                        {actionMenuId === user.id && (
                          <>
                            <div className="fixed inset-0 z-40" onClick={() => setActionMenuId(null)} />
                            <motion.div
                              initial={{ opacity: 0, scale: 0.95, y: -4 }}
                              animate={{ opacity: 1, scale: 1, y: 0 }}
                              exit={{ opacity: 0, scale: 0.95, y: -4 }}
                              className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg z-50 overflow-hidden py-1"
                            >
                              <button
                                onClick={() => {
                                  setSelectedUser(user);
                                  setNewRole(user.role as 'admin' | 'viewer');
                                  setIsEditRoleModalOpen(true);
                                  setActionMenuId(null);
                                }}
                                className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                              >
                                <Shield size={14} className="text-accent" />
                                Chỉnh quyền
                              </button>
                              {user.status === 'active' ? (
                                <button
                                  onClick={() => {
                                    setSelectedUser(user);
                                    setIsDisableDialogOpen(true);
                                    setActionMenuId(null);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-danger hover:bg-danger/5 transition-colors"
                                >
                                  <UserX size={14} />
                                  Vô hiệu hóa
                                </button>
                              ) : (
                                <button
                                  onClick={() => {
                                    handleEnableUser(user);
                                  }}
                                  className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-success hover:bg-success/5 transition-colors"
                                >
                                  <UserCheck size={14} />
                                  Kích hoạt lại
                                </button>
                              )}
                              {user.lastLogin === 'Chưa đăng nhập' && (
                                <>
                                  <div className="my-1 border-t border-slate-100 dark:border-slate-700" />
                                  <button
                                    onClick={() => setActionMenuId(null)}
                                    className="w-full flex items-center gap-2.5 px-3 py-2 text-xs text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors"
                                  >
                                    <Mail size={14} className="text-slate-400 dark:text-slate-500" />
                                    Gửi lại email mời
                                  </button>
                                </>
                              )}
                            </motion.div>
                          </>
                        )}
                      </AnimatePresence>
                    </div>
                  </td>
                </tr>
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
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                <h3 className="text-lg font-semibold">Thêm user vào Hub {activeHub?.name}</h3>
                <button onClick={() => setIsAddModalOpen(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 space-y-4">
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên đầy đủ</label>
                  <input type="text" placeholder="Nguyễn Văn A" className="input-field w-full" value={newUserName} onChange={e => setNewUserName(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Email</label>
                  <input type="email" placeholder="nva@medinet.vn" className="input-field w-full" value={newUserEmail} onChange={e => setNewUserEmail(e.target.value)} />
                </div>
                <div className="space-y-1.5">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Quyền</label>
                  <div className="flex gap-4">
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="role" value="admin" checked={newUserRole === 'admin'} onChange={() => setNewUserRole('admin')} className="text-accent focus:ring-accent" />
                      <span className="text-sm text-slate-700 dark:text-slate-200">Admin Hub Dự Án</span>
                    </label>
                    <label className="flex items-center gap-2 cursor-pointer">
                      <input type="radio" name="role" value="viewer" checked={newUserRole === 'viewer'} onChange={() => setNewUserRole('viewer')} className="text-accent focus:ring-accent" />
                      <span className="text-sm text-slate-700 dark:text-slate-200">Viewer</span>
                    </label>
                  </div>
                </div>
                <p className="text-[11px] text-slate-400 dark:text-slate-500 italic">
                  * User sẽ nhận email mời đặt mật khẩu tại {activeHub?.subdomain}. Link có hiệu lực 24 giờ.
                </p>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsAddModalOpen(false)} className="btn-ghost">Hủy</button>
                <button onClick={handleCreateUser} disabled={actionLoading} className="btn-primary">
                  {actionLoading ? <Loader2 size={16} className="animate-spin" /> : null}
                  Tạo & Gửi Email Mời
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isDisableDialogOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsDisableDialogOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-sm glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">Vô hiệu hóa tài khoản?</h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  Vô hiệu hóa tài khoản <span className="font-bold text-slate-700 dark:text-slate-200">{selectedUser?.name}</span>? User sẽ không thể đăng nhập Hub này, dữ liệu giữ nguyên.
                </p>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsDisableDialogOpen(false)} className="btn-ghost">Hủy</button>
                <button onClick={handleDisableUser} disabled={actionLoading} className="btn-primary !bg-danger !shadow-none hover:!bg-danger/90">
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : null}
                  Vô hiệu hóa
                </button>
              </div>
            </motion.div>
          </div>
        )}

        {isEditRoleModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => setIsEditRoleModalOpen(false)}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                <h3 className="text-lg font-semibold">Chỉnh sửa quyền: {selectedUser?.name}</h3>
                <button onClick={() => setIsEditRoleModalOpen(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 space-y-6">
                <div className="flex items-center gap-4 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-100 dark:border-slate-700">
                  <div className="w-12 h-12 rounded-full bg-brand-indigo/10 flex items-center justify-center text-brand-indigo">
                    <Shield size={24} />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-900 dark:text-white">{selectedUser?.name}</p>
                    <p className="text-xs text-slate-500 dark:text-slate-400">{selectedUser?.email}</p>
                  </div>
                </div>

                <div className="space-y-3">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Chọn quyền mới cho Hub {activeHub?.name}</label>
                  <div className="grid grid-cols-1 gap-3">
                    <button
                      onClick={() => setNewRole('admin')}
                      className={cn(
                        "flex items-center justify-between p-4 rounded-xl border transition-all text-left",
                        newRole === 'admin'
                          ? "border-brand-indigo bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] ring-1 ring-brand-indigo"
                          : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800"
                      )}
                    >
                      <div>
                        <p className="text-sm font-bold text-slate-900 dark:text-white">Admin</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Toàn quyền quản lý Hub, User và Tài liệu.</p>
                      </div>
                      {newRole === 'admin' && <div className="w-5 h-5 rounded-full bg-brand-indigo flex items-center justify-center text-white"><CheckCircle2 size={12} /></div>}
                    </button>

                    <button
                      onClick={() => setNewRole('viewer')}
                      className={cn(
                        "flex items-center justify-between p-4 rounded-xl border transition-all text-left",
                        newRole === 'viewer'
                          ? "border-brand-indigo bg-brand-indigo/[0.03] dark:bg-brand-indigo/[0.08] ring-1 ring-brand-indigo"
                          : "border-slate-200 dark:border-slate-700 hover:border-slate-300 dark:hover:border-slate-600 bg-white dark:bg-slate-800"
                      )}
                    >
                      <div>
                        <p className="text-sm font-bold text-slate-900 dark:text-white">Viewer</p>
                        <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">Chỉ xem tài liệu và thực hiện các thao tác cơ bản.</p>
                      </div>
                      {newRole === 'viewer' && <div className="w-5 h-5 rounded-full bg-brand-indigo flex items-center justify-center text-white"><CheckCircle2 size={12} /></div>}
                    </button>
                  </div>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => setIsEditRoleModalOpen(false)} className="btn-ghost">Hủy</button>
                <button onClick={handleUpdateRole} disabled={actionLoading} className="btn-primary">
                  {actionLoading ? <Loader2 size={16} className="animate-spin mr-1" /> : null}
                  Lưu thay đổi
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default UserManagement;
