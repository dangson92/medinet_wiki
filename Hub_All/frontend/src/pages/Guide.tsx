import { useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { Plus, NotebookPen, Trash2, Pencil, Eye, Search, Loader2 } from 'lucide-react';
import { api, type GuideListItemAPI } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

const formatDateTime = (iso: string) => {
  const d = new Date(iso);
  return d.toLocaleString('vi-VN', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
};

export default function Guide() {
  const { user } = useAuth();
  const isAdmin = user?.user.role === 'admin';

  const [guides, setGuides] = useState<GuideListItemAPI[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refresh = async () => {
    setLoading(true);
    setError(null);
    const res = await api.listGuides();
    if (res.success && res.data) {
      setGuides(res.data);
    } else {
      setError(res.error?.message ?? 'Không tải được danh sách hướng dẫn.');
    }
    setLoading(false);
  };

  useEffect(() => {
    refresh();
  }, []);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return guides;
    return guides.filter((g) => g.title.toLowerCase().includes(q));
  }, [guides, query]);

  const handleDelete = async (id: string, title: string) => {
    if (!window.confirm(`Xoá bài hướng dẫn "${title || 'Không tiêu đề'}"?`)) return;
    const res = await api.deleteGuide(id);
    if (res.success) {
      refresh();
    } else {
      window.alert(res.error?.message ?? 'Xoá thất bại.');
    }
  };

  return (
    <div className="max-w-6xl mx-auto space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <div>
          <h1 className="text-headline-md font-bold text-on-surface dark:text-white">
            Hướng dẫn sử dụng
          </h1>
          <p className="text-body-sm text-on-surface-variant dark:text-slate-400 mt-1">
            Tài liệu hướng dẫn chung của hệ thống Medinet Wiki — mọi user đều xem được.
            {isAdmin ? ' Bạn là Admin: có thể viết, sửa, xoá.' : ' Chỉ Admin được sửa.'}
          </p>
        </div>
        {isAdmin && (
          <Link
            to="/guide/new"
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-sm hover:bg-primary-container transition-all shadow-sm shrink-0"
          >
            <Plus size={16} strokeWidth={2.5} />
            <span>Viết bài mới</span>
          </Link>
        )}
      </div>

      <div className="m3-card p-4 space-y-4">
        <div className="relative">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant pointer-events-none"
          />
          <input
            type="search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Tìm theo tiêu đề..."
            className="w-full pl-9 pr-3 py-2 rounded-lg border border-outline-variant bg-white text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 dark:bg-slate-800 dark:border-slate-700 dark:text-white"
          />
        </div>

        {loading ? (
          <div className="text-center py-12">
            <Loader2 size={28} className="mx-auto animate-spin text-primary" />
            <p className="mt-3 text-body-sm text-on-surface-variant dark:text-slate-400">
              Đang tải danh sách hướng dẫn...
            </p>
          </div>
        ) : error ? (
          <div className="text-center py-12">
            <p className="text-body-sm font-semibold text-error">{error}</p>
            <button
              type="button"
              onClick={refresh}
              className="mt-3 px-3 py-1.5 rounded-lg border border-outline-variant text-body-sm font-semibold text-on-surface-variant hover:text-primary hover:border-primary/40 dark:border-slate-700"
            >
              Thử lại
            </button>
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-center py-12">
            <NotebookPen size={40} className="mx-auto text-on-surface-variant dark:text-slate-500" />
            <p className="mt-3 text-body-sm font-semibold text-on-surface dark:text-white">
              {guides.length === 0 ? 'Chưa có bài hướng dẫn nào' : 'Không khớp tìm kiếm'}
            </p>
            <p className="mt-1 text-[12px] text-on-surface-variant dark:text-slate-400">
              {guides.length === 0
                ? isAdmin
                  ? 'Bấm "Viết bài mới" để bắt đầu soạn bài hướng dẫn đầu tiên.'
                  : 'Admin chưa đăng bài hướng dẫn nào.'
                : 'Thử từ khoá khác hoặc xoá ô tìm kiếm.'}
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-outline-variant dark:divide-slate-700">
            {filtered.map((g) => (
              <li
                key={g.id}
                className="py-3 flex items-start gap-3 hover:bg-surface-container-low dark:hover:bg-slate-800/50 rounded-lg px-2 -mx-2 transition-colors"
              >
                <div className="flex-1 min-w-0">
                  <Link
                    to={`/guide/${g.id}`}
                    className="text-body-md font-bold text-on-surface dark:text-white hover:text-primary truncate block"
                  >
                    {g.title || '(Không tiêu đề)'}
                  </Link>
                  <p className="text-[11px] text-outline dark:text-slate-500 mt-1">
                    Cập nhật: {formatDateTime(g.updated_at)}
                  </p>
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <Link
                    to={`/guide/${g.id}`}
                    className="p-2 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-low dark:hover:bg-slate-700 transition-colors"
                    title="Xem"
                  >
                    <Eye size={16} />
                  </Link>
                  {isAdmin && (
                    <>
                      <Link
                        to={`/guide/${g.id}/edit`}
                        className="p-2 rounded-lg text-on-surface-variant hover:text-primary hover:bg-surface-container-low dark:hover:bg-slate-700 transition-colors"
                        title="Sửa"
                      >
                        <Pencil size={16} />
                      </Link>
                      <button
                        type="button"
                        onClick={() => handleDelete(g.id, g.title)}
                        className="p-2 rounded-lg text-on-surface-variant hover:text-error hover:bg-error/10 transition-colors"
                        title="Xoá"
                      >
                        <Trash2 size={16} />
                      </button>
                    </>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
