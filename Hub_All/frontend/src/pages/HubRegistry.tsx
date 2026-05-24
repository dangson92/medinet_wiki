import React, { useState, useEffect, useMemo, useCallback } from 'react';
import type { Hub } from '../types';
import { cn, getHubUrl } from '../lib/utils';
import { Plus, Edit2, Power, X, Search, Loader2, AlertTriangle } from 'lucide-react';
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
  const [confirmName, setConfirmName] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [currentPage, setCurrentPage] = useState(1);
  const [saving, setSaving] = useState(false);
  const itemsPerPage = 10;

  // Form state — chỉ metadata (v3.0 hub provision qua `make hub-add` CLI)
  const [formData, setFormData] = useState({ name: '', code: '', description: '' });

  const resetForm = () => setFormData({ name: '', code: '', description: '' });

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

  const handleSaveHub = async () => {
    setSaving(true);
    try {
      const res = await api.createHub({
        name: formData.name,
        code: formData.code,
        // Backend HubResponse.subdomain still NOT NULL (legacy Phase 5 migration 0003)
        // — auto-fill = code; UI derives URL via getHubUrl() instead.
        subdomain: formData.code,
        description: formData.description || undefined,
        chroma_collection: '',
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
    setFormData({ name: hub.name, code: hub.code, description: '' });
    setIsEditModalOpen(true);
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="text-h1 font-bold text-slate-900 dark:text-white tracking-tight">Hub Registry</h1>
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
                <th className="px-5 py-3 text-xs font-medium text-slate-500 dark:text-slate-400">URL Hub</th>
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
                  <td className="px-5 py-4 text-sm text-accent font-medium font-mono">{getHubUrl(hub.code)}</td>
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
              <div className="p-6 overflow-y-auto max-h-[70vh] space-y-6">
                <div className="flex items-start gap-3 p-4 rounded-xl bg-amber-50 dark:bg-amber-500/10 border border-amber-200 dark:border-amber-500/30">
                  <AlertTriangle size={18} className="text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-800 dark:text-amber-200 space-y-1">
                    <p className="font-semibold">Form này chỉ ghi metadata Hub vào DB.</p>
                    <p>
                      Hub thực sự truy cập được sau khi admin chạy <code className="bg-amber-100 dark:bg-amber-500/20 px-1 py-0.5 rounded font-mono">make hub-add HUB={'<mã hub>'}</code> trên VPS
                      để provision DB + container + Caddy regex. Xem <code className="bg-amber-100 dark:bg-amber-500/20 px-1 py-0.5 rounded font-mono">VPS_DEPLOY.md</code> §9.4.
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Tên Hub</label>
                      <input type="text" placeholder="Ví dụ: Tâm Đạo Y Quán" className="input-field w-full" value={formData.name} onChange={e => setFormData(f => ({ ...f, name: e.target.value }))} />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mã Hub</label>
                      <input
                        type="text"
                        placeholder="tamdao"
                        className="input-field w-full font-mono"
                        value={formData.code}
                        onChange={e => setFormData(f => ({ ...f, code: e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '') }))}
                      />
                      <p className="text-[11px] text-slate-400 dark:text-slate-500">Chỉ chữ thường, số và dấu gạch dưới. Tối đa 16 ký tự.</p>
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">URL Hub</label>
                      <div className="input-field w-full bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-mono text-sm cursor-not-allowed">
                        {formData.code ? getHubUrl(formData.code) : `${getHubUrl(null)}/<mã hub>`}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mô tả</label>
                      <textarea placeholder="Mô tả ngắn gọn về Hub..." className="input-field w-full h-[180px] resize-none" value={formData.description} onChange={e => setFormData(f => ({ ...f, description: e.target.value }))} />
                    </div>
                  </div>
                </div>
              </div>
              <div className="p-4 bg-slate-50 dark:bg-slate-800/50 flex justify-end gap-3 border-t border-slate-200/50 dark:border-slate-700/50">
                <button onClick={() => { setIsAddModalOpen(false); resetForm(); }} className="btn-ghost">Hủy</button>
                <button
                  onClick={handleSaveHub}
                  disabled={saving || !formData.name.trim() || !formData.code.trim()}
                  className={cn("btn-primary", (saving || !formData.name.trim() || !formData.code.trim()) && "opacity-50 cursor-not-allowed")}
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
                      <input type="text" className="input-field w-full bg-slate-50 dark:bg-slate-800 cursor-not-allowed font-mono" value={formData.code} disabled />
                    </div>
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">URL Hub</label>
                      <div className="input-field w-full bg-slate-50 dark:bg-slate-800 text-slate-500 dark:text-slate-400 font-mono text-sm cursor-not-allowed">
                        {getHubUrl(formData.code)}
                      </div>
                    </div>
                  </div>
                  <div className="space-y-4">
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium text-slate-600 dark:text-slate-300">Mô tả</label>
                      <textarea placeholder="Mô tả ngắn gọn về Hub..." className="input-field w-full h-[180px] resize-none" value={formData.description} onChange={e => setFormData(f => ({ ...f, description: e.target.value }))} />
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
