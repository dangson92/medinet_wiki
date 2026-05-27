import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { ArrowLeft, Pencil, Trash2, Loader2, Clock } from 'lucide-react';
import { api, type GuideAPI } from '../services/api';
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

export default function GuideView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.user.role === 'admin';

  const [guide, setGuide] = useState<GuideAPI | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!id) return;
    let cancelled = false;
    setLoading(true);
    api.getGuide(id).then((res) => {
      if (cancelled) return;
      if (res.success && res.data) {
        setGuide(res.data);
      } else if (res.error?.code === 'NOT_FOUND') {
        setNotFound(true);
      } else {
        setError(res.error?.message ?? 'Không tải được bài hướng dẫn.');
      }
      setLoading(false);
    });
    return () => {
      cancelled = true;
    };
  }, [id]);

  const handleDelete = async () => {
    if (!guide) return;
    if (!window.confirm(`Xoá bài hướng dẫn "${guide.title || 'Không tiêu đề'}"?`)) return;
    const res = await api.deleteGuide(guide.id);
    if (res.success) {
      navigate('/guide');
    } else {
      window.alert(res.error?.message ?? 'Xoá thất bại.');
    }
  };

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto m3-card p-12 text-center">
        <Loader2 size={28} className="mx-auto animate-spin text-primary" />
        <p className="mt-3 text-body-sm text-on-surface-variant dark:text-slate-400">
          Đang tải bài hướng dẫn...
        </p>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="max-w-3xl mx-auto m3-card p-6 text-center">
        <p className="text-body-md font-semibold text-on-surface dark:text-white">
          Không tìm thấy bài hướng dẫn
        </p>
        <p className="text-body-sm text-on-surface-variant dark:text-slate-400 mt-1">
          Bài có thể đã bị xoá.
        </p>
        <Link
          to="/guide"
          className="inline-flex items-center gap-2 mt-4 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-sm hover:bg-primary-container transition-all"
        >
          <ArrowLeft size={16} strokeWidth={2.5} />
          <span>Về danh sách</span>
        </Link>
      </div>
    );
  }

  if (error) {
    return (
      <div className="max-w-3xl mx-auto m3-card p-6">
        <p role="alert" className="text-body-sm font-semibold text-error">
          {error}
        </p>
        <Link
          to="/guide"
          className="inline-flex items-center gap-2 mt-4 px-3 py-1.5 rounded-lg border border-outline-variant text-body-sm font-semibold text-on-surface-variant hover:text-primary hover:border-primary/40 dark:border-slate-700"
        >
          <ArrowLeft size={14} />
          <span>Về danh sách</span>
        </Link>
      </div>
    );
  }

  if (!guide) return null;

  return (
    <div className="max-w-4xl mx-auto space-y-4">
      <div className="flex items-center justify-between gap-3">
        <Link
          to="/guide"
          className="inline-flex items-center gap-2 text-body-sm font-semibold text-on-surface-variant hover:text-primary transition-colors"
        >
          <ArrowLeft size={16} />
          <span>Về danh sách</span>
        </Link>
        {isAdmin && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={handleDelete}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-outline-variant text-on-surface-variant hover:text-error hover:border-error/40 hover:bg-error/5 transition-colors text-body-sm font-semibold dark:border-slate-700"
            >
              <Trash2 size={16} />
              <span className="hidden sm:inline">Xoá</span>
            </button>
            <Link
              to={`/guide/${guide.id}/edit`}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-sm hover:bg-primary-container transition-all shadow-sm"
            >
              <Pencil size={16} strokeWidth={2.5} />
              <span>Sửa bài</span>
            </Link>
          </div>
        )}
      </div>

      <article className="m3-card p-6 space-y-4">
        <header className="space-y-2 border-b border-outline-variant pb-4 dark:border-slate-700">
          <h1 className="text-headline-md font-bold text-on-surface dark:text-white">
            {guide.title || '(Không tiêu đề)'}
          </h1>
          <div className="flex items-center gap-1.5 text-[12px] text-on-surface-variant dark:text-slate-400">
            <Clock size={12} />
            <span>Cập nhật: {formatDateTime(guide.updated_at)}</span>
          </div>
        </header>

        {guide.content ? (
          <div
            className="prose dark:prose-invert max-w-none"
            // eslint-disable-next-line react/no-danger
            dangerouslySetInnerHTML={{ __html: guide.content }}
          />
        ) : (
          <p className="text-body-sm text-on-surface-variant italic dark:text-slate-400">
            Bài hướng dẫn chưa có nội dung.
          </p>
        )}
      </article>
    </div>
  );
}
