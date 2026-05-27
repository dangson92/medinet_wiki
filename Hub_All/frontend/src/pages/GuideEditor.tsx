import { useEffect, useState } from 'react';
import { useNavigate, useParams, Link } from 'react-router-dom';
import { ArrowLeft, Save, Trash2, Check, Loader2 } from 'lucide-react';
import RichTextEditor from '../components/RichTextEditor';
import { api } from '../services/api';
import { useAuth } from '../contexts/AuthContext';

export default function GuideEditor() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { user } = useAuth();
  const isAdmin = user?.user.role === 'admin';

  const [currentId, setCurrentId] = useState<string | undefined>(id);
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(Boolean(id));
  const [notFound, setNotFound] = useState(false);
  const [saving, setSaving] = useState(false);
  const [justSaved, setJustSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Non-admin lạc vào /guide/new hoặc /guide/:id/edit → đẩy về list/view.
  useEffect(() => {
    if (user && !isAdmin) {
      navigate(id ? `/guide/${id}` : '/guide', { replace: true });
    }
  }, [user, isAdmin, id, navigate]);

  useEffect(() => {
    if (!id) {
      setTitle('');
      setContent('');
      setNotFound(false);
      setCurrentId(undefined);
      setLoading(false);
      return;
    }
    let cancelled = false;
    setLoading(true);
    api.getGuide(id).then((res) => {
      if (cancelled) return;
      if (res.success && res.data) {
        setCurrentId(res.data.id);
        setTitle(res.data.title);
        setContent(res.data.content);
        setNotFound(false);
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

  const handleSave = async () => {
    if (!title.trim()) {
      window.alert('Vui lòng nhập tiêu đề.');
      return;
    }
    setSaving(true);
    setError(null);
    const payload = { title: title.trim(), content };
    const res = currentId
      ? await api.updateGuide(currentId, payload)
      : await api.createGuide(payload);
    setSaving(false);
    if (res.success && res.data) {
      // Tạo mới → quay về danh sách (user yêu cầu).
      // Sửa → giữ ở editor + flash "Đã lưu" 2s.
      if (!currentId) {
        navigate('/guide');
        return;
      }
      setCurrentId(res.data.id);
      setJustSaved(true);
      setTimeout(() => setJustSaved(false), 2000);
    } else {
      setError(res.error?.message ?? 'Lưu thất bại.');
    }
  };

  const handleDelete = async () => {
    if (!currentId) return;
    if (!window.confirm(`Xoá bài hướng dẫn "${title || 'Không tiêu đề'}"?`)) return;
    const res = await api.deleteGuide(currentId);
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

  return (
    <div className="max-w-5xl mx-auto space-y-4">
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
            {currentId && (
              <button
                type="button"
                onClick={handleDelete}
                disabled={saving}
                className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-outline-variant text-on-surface-variant hover:text-error hover:border-error/40 hover:bg-error/5 transition-colors text-body-sm font-semibold dark:border-slate-700 disabled:opacity-50"
              >
                <Trash2 size={16} />
                <span className="hidden sm:inline">Xoá</span>
              </button>
            )}
            <button
              type="button"
              onClick={handleSave}
              disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2 bg-primary text-on-primary rounded-lg font-bold text-body-sm hover:bg-primary-container transition-all shadow-sm disabled:opacity-60"
            >
              {saving ? (
                <Loader2 size={16} className="animate-spin" />
              ) : justSaved ? (
                <Check size={16} strokeWidth={2.5} />
              ) : (
                <Save size={16} strokeWidth={2.5} />
              )}
              <span>{saving ? 'Đang lưu...' : justSaved ? 'Đã lưu' : currentId ? 'Lưu thay đổi' : 'Tạo bài'}</span>
            </button>
          </div>
        )}
      </div>

      {error && (
        <div
          role="alert"
          className="p-3 rounded-lg bg-error/10 text-error border border-error/20 text-body-sm font-semibold"
        >
          {error}
        </div>
      )}

      <div className="m3-card p-4 space-y-3">
        <div>
          <label
            htmlFor="guide-title"
            className="block text-body-sm font-semibold text-on-surface dark:text-white mb-1.5"
          >
            Tiêu đề
          </label>
          <input
            id="guide-title"
            type="text"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="Ví dụ: Cách nạp tri thức mới"
            className="w-full px-3 py-2 rounded-lg border border-outline-variant bg-white text-on-surface placeholder:text-outline focus:outline-none focus:ring-2 focus:ring-primary/20 focus:border-primary/40 dark:bg-slate-800 dark:border-slate-700 dark:text-white"
          />
        </div>

        <div>
          <label className="block text-body-sm font-semibold text-on-surface dark:text-white mb-1.5">
            Nội dung
          </label>
          <RichTextEditor
            content={content}
            onChange={setContent}
            placeholder="Bắt đầu viết hướng dẫn..."
          />
        </div>
      </div>
    </div>
  );
}
