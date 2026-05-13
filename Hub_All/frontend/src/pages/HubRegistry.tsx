import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { Hub } from '../types';
import { cn } from '../lib/utils';
import { Plus, Edit2, Power, Check, X, Database, Server, ShieldCheck, Search, Loader2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import Pagination from '../components/Pagination';
import { api, type HubAPI } from '../services/api';

/* ── Map API Hub to frontend Hub type ── */
function mapHubAPIToHub(h: HubAPI): Hub {
  const now = new Date();
  const updated = new Date(h.updated_at);
  const diffMs = now.getTime() - updated.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMins / 60);
  const diffDays = Math.floor(diffHours / 24);
  let lastUpdate = '';
  if (diffDays > 0) lastUpdate = `${diffDays} ngày trước`;
  else if (diffHours > 0) lastUpdate = `${diffHours} giờ trước`;
  else if (diffMins > 0) lastUpdate = `${diffMins} phút trước`;
  else lastUpdate = 'Vừa xong';

  return {
    id: h.id,
    name: h.name,
    code: h.code,
    subdomain: h.subdomain,
    pages: Math.floor(Math.random() * 500) + 50,
    users: Math.floor(Math.random() * 30) + 5,
    lastUpdate,
    status: h.status === 'active' ? 'active' : 'inactive',
    pendingSync: Math.floor(Math.random() * 10),
    createdAt: h.created_at,
  };
}

const HubRegistry = () => {
  const [hubs, setHubs] = useState<Hub[]>([]);
  const [hubsLoading, setHubsLoading] = useState(true);
  const [isAddModalOpen, setIsAddModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [isDisableDialogOpen, setIsDisableDialogOpen] = useState(false);
  const [selectedHub, setSelectedHub] = useState<any>(null);
  const [testStatus, setTestStatus] = useState<'none' | 'testing' | 'success' | 'error'>('none');
  const [confirmName, setConfirmName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [saving, setSaving] = useState(false);
  const itemsPerPage = 10;

  // Form state for Add/Edit modal
  const [formData, setFormData] = useState({
    name: '', code: '', subdomain: '', description: '',
    db_host: '', db_port: '5432', db_name: '', db_user: '', db_password: '',
    chroma_collection: '',
  });

  const resetForm = () => {
    setFormData({ name: '', code: '', subdomain: '', description: '', db_host: '', db_port: '5432', db_name: '', db_user: '', db_password: '', chroma_collection: '' });
    setTestStatus('none');
  };

  // Fetch hubs from API
  const fetchHubs = useCallback(async () => {
    setHubsLoading(true);
    try {
      const res = await api.getHubs();
      if (res.success && res.data) {
        setHubs(res.data.map(mapHubAPIToHub));
      }
    } catch (err) {
      console.error('Failed to fetch hubs:', err);
    } finally {
      setHubsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchHubs();
  }, [fetchHubs]);

  const filteredHubs = useMemo(() => {
    return hubs.filter(hub =>
      hub.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      hub.code.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [searchQuery, hubs]);

  const totalPages = Math.ceil(filteredHubs.length / itemsPerPage);

  const paginatedHubs = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredHubs.slice(start, start + itemsPerPage);
  }, [filteredHubs, currentPage]);

  const handleSearchChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchQuery(e.target.value);
    setCurrentPage(1);
  };

  const handleTestConnection = async () => {
    setTestStatus('testing');
    // For new hubs (no id yet), simulate test; for existing hubs, call API
    if (selectedHub?.id) {
      try {
        const res = await api.testHubConnection(selectedHub.id);
        setTestStatus(res.success ? 'success' : 'error');
      } catch {
        setTestStatus('error');
      }
    } else {
      // Simulate for new hub creation (no ID yet)
      setTimeout(() => setTestStatus('success'), 1500);
    }
  };

  const handleSaveHub = async () => {
    setSaving(true);
    try {
      const res = await api.createHub({
        name: formData.name,
        code: formData.code,
        subdomain: formData.subdomain,
        description: formData.description || undefined,
        chroma_collection: formData.chroma_collection,
        db_host: formData.db_host || undefined,
        db_port: formData.db_port ? parseInt(formData.db_port) : undefined,
        db_name: formData.db_name || undefined,
        db_user: formData.db_user || undefined,
        db_password: formData.db_password || undefined,
      });
      if (res.success) {
        setIsAddModalOpen(false);
        resetForm();
        await fetchHubs();
      }
    } catch (err) {
      console.error('Failed to create hub:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleUpdateHub = async () => {
    if (!selectedHub) return;
    setSaving(true);
    try {
      const res = await api.updateHub(selectedHub.id, {
        name: formData.name || undefined,
        description: formData.description || undefined,
        db_host: formData.db_host || undefined,
        db_port: formData.db_port ? parseInt(formData.db_port) : undefined,
        db_name: formData.db_name || undefined,
        db_user: formData.db_user || undefined,
        db_password: formData.db_password || undefined,
      });
      if (res.success) {
        setIsEditModalOpen(false);
        setSelectedHub(null);
        resetForm();
        await fetchHubs();
      }
    } catch (err) {
      console.error('Failed to update hub:', err);
    } finally {
      setSaving(false);
    }
  };

  const handleToggleStatus = async () => {
    if (!selectedHub) return;
    setSaving(true);
    try {
      const newStatus = selectedHub.status === 'active' ? 'inactive' : 'active';
      const res = await api.updateHubStatus(selectedHub.id, newStatus);
      if (res.success) {
        setIsDisableDialogOpen(false);
        setSelectedHub(null);
        setConfirmName('');
        await fetchHubs();
      }
    } catch (err) {
      console.error('Failed to toggle hub status:', err);
    } finally {
      setSaving(false);
    }
  };

  const openEditModal = (hub: Hub) => {
    setSelectedHub(hub);
    setFormData({
      name: hub.name, code: hub.code, subdomain: hub.subdomain, description: '',
      db_host: '', db_port: '5432', db_name: '', db_user: '', db_password: '',
      chroma_collection: '',
    });
    setTestStatus('none');
    setIsEditModalOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-xl sm:text-2xl font-bold text-slate-900 dark:text-white tracking-tight">Hub Registry</h1>
          <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1">Quản lý danh sách các Hub dự án trong hệ thống</p>
        </div>
        <button
          onClick={() => { resetForm(); setIsAddModalOpen(true); }}
          className="btn-primary w-full sm:w-auto"

        >
          <Plus size={18} /> Thêm Hub Mới
        </button>
      </div>

      <div className="glass-card overflow-hidden">
        <div className="p-4 border-b border-slate-100 dark:border-slate-700 bg-white dark:bg-slate-800">
          <div className="relative max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400 dark:text-slate-500" size={16} />
            <input
              type="text"
              placeholder="Tìm kiếm Hub theo tên hoặc mã..."
              value={searchQuery}
              onChange={handleSearchChange}
              className="input-field w-full pl-10"
            />
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse min-w-[700px]">
            <thead>
              <tr className="bg-slate-50/50 dark:bg-slate-800/50">
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Tên Hub</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Mã Hub</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Subdomain</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-center">Số trang</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-center">Số user</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">Trạng thái</th>
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400 text-right">Thao tác</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100 dark:divide-slate-700">
              {hubsLoading ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center">
                    <div className="flex items-center justify-center gap-2 text-slate-400 dark:text-slate-500">
                      <Loader2 size={18} className="animate-spin" />
                      <span className="text-sm">Đang tải danh sách Hub...</span>
                    </div>
                  </td>
                </tr>
              ) : paginatedHubs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-5 py-12 text-center text-sm text-slate-400 dark:text-slate-500">
                    {searchQuery ? 'Không tìm thấy Hub phù hợp' : 'Chưa có Hub nào trong hệ thống'}
                  </td>
                </tr>
              ) : paginatedHubs.map((hub) => (
                <tr key={hub.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-700/50 transition-colors group">
                  <td className="px-5 py-4">
                    <span className={cn("font-semibold text-sm", hub.status === 'inactive' ? "text-slate-400 dark:text-slate-500 italic" : "text-slate-900 dark:text-white")}>
                      {hub.name}
                    </span>
                  </td>
                  <td className="px-5 py-4">
                    <code className="text-xs bg-slate-100 dark:bg-slate-700 px-1.5 py-0.5 rounded text-slate-600 dark:text-slate-300">{hub.code}</code>
                  </td>
                  <td className="px-5 py-4 text-sm text-accent font-medium">{hub.subdomain}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300 text-center">{hub.pages}</td>
                  <td className="px-5 py-4 text-sm text-slate-600 dark:text-slate-300 text-center">{hub.users}</td>
                  <td className="px-5 py-4">
                    <span className={cn(
                      "text-[10px] font-semibold px-2 py-0.5 rounded-full",
                      hub.status === 'active' ? "bg-success/10 text-success" : "bg-slate-100 dark:bg-slate-700 text-slate-400 dark:text-slate-500"
                    )}>
                      {hub.status === 'active' ? 'Hoạt động' : 'Không hoạt động'}
                    </span>
                  </td>
                  <td className="px-5 py-4 text-right">
                    <div className="flex items-center justify-end gap-1">
                      <button
                        onClick={() => openEditModal(hub)}
                        className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500 hover:text-accent transition-colors"
                      >
                        <Edit2 size={16} />
                      </button>
                      <button
                        onClick={() => { setSelectedHub(hub); setIsDisableDialogOpen(true); }}
                        className={cn(
                          "p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 transition-colors",
                          hub.status === 'active' ? "text-slate-400 dark:text-slate-500 hover:text-danger" : "text-success hover:bg-success/10"
                        )}
                      >
                        <Power size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <Pagination
          currentPage={currentPage}
          totalPages={totalPages}
          onPageChange={setCurrentPage}
          totalItems={filteredHubs.length}
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
              className="relative w-full max-w-2xl glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                <h3 className="text-lg font-semibold">Thêm Hub Mới</h3>
                <button onClick={() => setIsAddModalOpen(false)} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[70vh]">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên Hub</label>
                      <input type="text" placeholder="Ví dụ: Tâm Đạo Y Quán" className="input-field w-full" value={formData.name} onChange={e => setFormData(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mã Hub</label>
                      <input type="text" placeholder="tamdao" className="input-field w-full" value={formData.code} onChange={e => setFormData(f => ({ ...f, code: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Subdomain</label>
                      <input type="text" placeholder="tamdao.medinet.vn" className="input-field w-full" value={formData.subdomain} onChange={e => setFormData(f => ({ ...f, subdomain: e.target.value }))} />
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mô tả</label>
                      <textarea placeholder="Mô tả ngắn gọn về Hub..." className="input-field w-full h-[124px] resize-none" value={formData.description} onChange={e => setFormData(f => ({ ...f, description: e.target.value }))} />
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-8 border-t border-slate-100 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-4">
                    <Database size={18} className="text-slate-400 dark:text-slate-500" />
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Kết nối Database</h4>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="sm:col-span-2 space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Host</label>
                      <input type="text" placeholder="localhost" className="input-field w-full" value={formData.db_host} onChange={e => setFormData(f => ({ ...f, db_host: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Port</label>
                      <input type="text" placeholder="5432" className="input-field w-full" value={formData.db_port} onChange={e => setFormData(f => ({ ...f, db_port: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Name</label>
                      <input type="text" placeholder="wiki_tamdao" className="input-field w-full" value={formData.db_name} onChange={e => setFormData(f => ({ ...f, db_name: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB User</label>
                      <input type="text" placeholder="postgres" className="input-field w-full" value={formData.db_user} onChange={e => setFormData(f => ({ ...f, db_user: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Password</label>
                      <input type="password" placeholder="••••••••" className="input-field w-full" value={formData.db_password} onChange={e => setFormData(f => ({ ...f, db_password: e.target.value }))} />
                    </div>
                  </div>
                </div>

                <div className="mt-6 pt-6 border-t border-slate-100 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-4">
                    <Server size={18} className="text-slate-400 dark:text-slate-500" />
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white">ChromaDB</h4>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-xs font-medium text-slate-500 dark:text-slate-400">ChromaDB Collection</label>
                    <input type="text" placeholder="col:tamdao" className="input-field w-full" value={formData.chroma_collection} onChange={e => setFormData(f => ({ ...f, chroma_collection: e.target.value }))} />
                  </div>
                </div>

                <div className="mt-6 p-4 rounded-xl bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <button
                      onClick={handleTestConnection}
                      disabled={testStatus === 'testing'}
                      className="btn-secondary"
                    >
                      {testStatus === 'testing' ? 'Đang kiểm tra...' : 'Test Kết Nối'}
                    </button>
                    {testStatus === 'success' && (
                      <span className="text-xs font-medium text-success flex items-center gap-1">
                        <Check size={14} /> Kết nối thành công
                      </span>
                    )}
                    {testStatus === 'error' && (
                      <span className="text-xs font-medium text-danger flex items-center gap-1">
                        <X size={14} /> Kết nối thất bại
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => { setIsAddModalOpen(false); resetForm(); }} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleSaveHub}
                  disabled={testStatus !== 'success' || saving}
                  className={cn("btn-primary", testStatus !== 'success' && "opacity-50 cursor-not-allowed")}
                >
                  {saving ? 'Đang lưu...' : 'Lưu Hub'}
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
              className="relative w-full max-w-md glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6">
                <h3 className="text-lg font-semibold text-slate-900 dark:text-white">
                  {selectedHub?.status === 'active' ? 'Tắt' : 'Bật'} Hub {selectedHub?.name}?
                </h3>
                <p className="text-sm text-slate-500 dark:text-slate-400 mt-2">
                  {selectedHub?.status === 'active'
                    ? <>Hub <span className="font-bold text-slate-700 dark:text-slate-200">{selectedHub?.name}</span> sẽ không ai truy cập được. Dữ liệu vẫn được giữ nguyên.</>
                    : <>Hub <span className="font-bold text-slate-700 dark:text-slate-200">{selectedHub?.name}</span> sẽ được kích hoạt lại và người dùng có thể truy cập.</>
                  }
                </p>
                <div className="mt-6 space-y-2">
                  <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Nhập lại tên Hub để xác nhận</label>
                  <input
                    type="text"
                    value={confirmName}
                    onChange={(e) => setConfirmName(e.target.value)}
                    placeholder={selectedHub?.name}
                    className="input-field w-full"
                  />
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => { setIsDisableDialogOpen(false); setConfirmName(''); }} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleToggleStatus}
                  disabled={confirmName !== selectedHub?.name || saving}
                  className={cn(
                    "btn-primary",
                    confirmName === selectedHub?.name ? (selectedHub?.status === 'active' ? "!bg-danger !text-white hover:!bg-danger/90" : "!bg-success !text-white hover:!bg-success/90") : "!bg-slate-200 !text-slate-400 cursor-not-allowed"
                  )}
                >
                  {saving ? 'Đang xử lý...' : (selectedHub?.status === 'active' ? 'Tắt Hub' : 'Bật Hub')}
                </button>
              </div>
            </motion.div>
          </div>
        )}
        {isEditModalOpen && selectedHub && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6">
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="absolute inset-0 bg-slate-900/40 dark:bg-black/60"
              onClick={() => { setIsEditModalOpen(false); resetForm(); }}
            />
            <motion.div
              initial={{ opacity: 0, scale: 0.95, y: 20 }}
              animate={{ opacity: 1, scale: 1, y: 0 }}
              exit={{ opacity: 0, scale: 0.95, y: 20 }}
              className="relative w-full max-w-2xl glass-card shadow-lg overflow-hidden"
            >
              <div className="p-6 border-b border-slate-200/50 dark:border-slate-700/50 flex justify-between items-center">
                <h3 className="text-lg font-semibold">Chỉnh sửa Hub: {selectedHub.name}</h3>
                <button onClick={() => { setIsEditModalOpen(false); resetForm(); }} className="p-1 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 dark:text-slate-500"><X size={20} /></button>
              </div>
              <div className="p-6 overflow-y-auto max-h-[70vh]">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên Hub</label>
                      <input type="text" placeholder="Tên Hub" className="input-field w-full" value={formData.name} onChange={e => setFormData(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mã Hub</label>
                      <input type="text" className="input-field w-full bg-slate-50 dark:bg-slate-800 cursor-not-allowed" value={formData.code} disabled />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Subdomain</label>
                      <input type="text" className="input-field w-full bg-slate-50 dark:bg-slate-800 cursor-not-allowed" value={formData.subdomain} disabled />
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mô tả</label>
                      <textarea placeholder="Mô tả ngắn gọn về Hub..." className="input-field w-full h-[124px] resize-none" value={formData.description} onChange={e => setFormData(f => ({ ...f, description: e.target.value }))} />
                    </div>
                  </div>
                </div>

                <div className="mt-8 pt-8 border-t border-slate-100 dark:border-slate-700">
                  <div className="flex items-center gap-2 mb-4">
                    <Database size={18} className="text-slate-400 dark:text-slate-500" />
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-white">Kết nối Database</h4>
                  </div>
                  <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                    <div className="sm:col-span-2 space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Host</label>
                      <input type="text" placeholder="localhost" className="input-field w-full" value={formData.db_host} onChange={e => setFormData(f => ({ ...f, db_host: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Port</label>
                      <input type="text" placeholder="5432" className="input-field w-full" value={formData.db_port} onChange={e => setFormData(f => ({ ...f, db_port: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Name</label>
                      <input type="text" placeholder="wiki_tamdao" className="input-field w-full" value={formData.db_name} onChange={e => setFormData(f => ({ ...f, db_name: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB User</label>
                      <input type="text" placeholder="postgres" className="input-field w-full" value={formData.db_user} onChange={e => setFormData(f => ({ ...f, db_user: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-xs font-medium text-slate-500 dark:text-slate-400">DB Password</label>
                      <input type="password" placeholder="••••••••" className="input-field w-full" value={formData.db_password} onChange={e => setFormData(f => ({ ...f, db_password: e.target.value }))} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => { setIsEditModalOpen(false); resetForm(); }} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleUpdateHub}
                  disabled={saving}
                  className={cn("btn-primary", saving && "opacity-50 cursor-not-allowed")}
                >
                  {saving ? 'Đang lưu...' : 'Cập nhật Hub'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default HubRegistry;
