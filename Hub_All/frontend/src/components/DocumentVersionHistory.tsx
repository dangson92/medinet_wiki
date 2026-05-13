import { useEffect, useState } from 'react';
import { api, type DocumentVersionAPI } from '../services/api';
import {
  Clock,
  Download,
  RotateCcw,
  FileText,
  Pin,
  Loader2,
  AlertCircle,
  RefreshCw,
  Pencil,
  UploadCloud,
} from 'lucide-react';

interface Props {
  documentId: string;
  /** Cho phép admin thực hiện restore. Viewer chỉ xem + tải. */
  canRestore?: boolean;
  /** Callback gọi sau khi restore thành công để parent refresh document. */
  onRestored?: () => void;
}

const CHANGE_TYPE_META: Record<DocumentVersionAPI['change_type'], { label: string; icon: typeof Clock; color: string }> = {
  reupload:     { label: 'Tải lại file', icon: UploadCloud, color: 'text-blue-600 bg-blue-50' },
  reextract:    { label: 'Reindex',       icon: RefreshCw,   color: 'text-purple-600 bg-purple-50' },
  content_edit: { label: 'Sửa nội dung',  icon: Pencil,      color: 'text-amber-600 bg-amber-50' },
  restore:      { label: 'Khôi phục',     icon: RotateCcw,   color: 'text-green-600 bg-green-50' },
};

function formatBytes(n: number): string {
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB';
  return n + ' B';
}

function formatTime(iso: string): string {
  try {
    return new Date(iso).toLocaleString('vi-VN', { dateStyle: 'short', timeStyle: 'short' });
  } catch {
    return iso;
  }
}

export default function DocumentVersionHistory({ documentId, canRestore = false, onRestored }: Props) {
  const [versions, setVersions] = useState<DocumentVersionAPI[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [restoringId, setRestoringId] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await api.listDocumentVersions(documentId);
      if (res.success && res.data) {
        setVersions(res.data.versions || []);
      } else {
        setError(res.error?.message || 'Không tải được lịch sử phiên bản');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Lỗi không xác định');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [documentId]);

  const handleDownload = (v: DocumentVersionAPI) => {
    const url = api.getDocumentVersionFileUrl(documentId, v.id);
    const token = localStorage.getItem('access_token');
    fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      .then(r => r.ok ? r.blob() : Promise.reject(new Error('Download lỗi')))
      .then(blob => {
        const objectUrl = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = objectUrl;
        a.download = `v${v.version_number}_${v.name}`;
        a.click();
        URL.revokeObjectURL(objectUrl);
      })
      .catch(err => alert('Tải file thất bại: ' + err.message));
  };

  const handleRestore = async (v: DocumentVersionAPI) => {
    if (!confirm(`Khôi phục tài liệu về phiên bản v${v.version_number}? Phiên bản hiện tại sẽ được lưu lại trước khi ghi đè.`)) {
      return;
    }
    setRestoringId(v.id);
    try {
      const res = await api.restoreDocumentVersion(documentId, v.id);
      if (res.success) {
        await load();
        onRestored?.();
      } else {
        alert('Khôi phục thất bại: ' + (res.error?.message || 'Không rõ lý do'));
      }
    } catch (e) {
      alert('Khôi phục thất bại: ' + (e instanceof Error ? e.message : 'Lỗi không xác định'));
    } finally {
      setRestoringId(null);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 text-gray-500">
        <Loader2 className="w-5 h-5 animate-spin mr-2" />
        Đang tải lịch sử phiên bản…
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-start gap-3 p-4 rounded-lg bg-red-50 text-red-700 border border-red-200">
        <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
        <div className="text-sm">{error}</div>
      </div>
    );
  }

  if (versions.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500">
        <Clock className="w-10 h-10 mx-auto mb-3 opacity-40" />
        <p className="text-sm">Chưa có phiên bản nào được lưu cho tài liệu này.</p>
        <p className="text-xs mt-1 opacity-70">
          Phiên bản sẽ được tự động tạo khi tải lại file, sửa nội dung hoặc reindex.
        </p>
      </div>
    );
  }

  // versions đã sort theo version_number DESC từ BE.
  // Đánh dấu "current" cho version cao nhất (đại diện trạng thái live trước khi
  // mutate gần nhất). Thật ra version cao nhất là snapshot CỦA trạng thái cũ
  // ngay trước thay đổi gần nhất — không phải live. Vì thế chỉ hiển thị badge
  // "Gốc" cho is_original, không có badge "Hiện tại".

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-xs text-gray-500">
          Lưu tối đa 5 phiên bản: <strong>3 gốc đầu tiên</strong> (v1, v2, v3) + <strong>2 phiên bản gần nhất</strong>.
          Các phiên bản giữa được dọn tự động.
        </p>
        <button
          onClick={load}
          className="text-xs text-blue-600 hover:text-blue-700 flex items-center gap-1"
        >
          <RefreshCw className="w-3 h-3" /> Tải lại
        </button>
      </div>

      <ol className="relative border-l-2 border-gray-200 ml-3 space-y-4">
        {versions.map((v) => {
          const meta = CHANGE_TYPE_META[v.change_type] ?? { label: v.change_type, icon: FileText, color: 'text-gray-600 bg-gray-50' };
          const Icon = meta.icon;
          return (
            <li key={v.id} className="ml-6">
              <span className="absolute -left-[11px] flex items-center justify-center w-5 h-5 bg-white rounded-full ring-4 ring-white">
                <span className={`w-3 h-3 rounded-full ${v.is_original ? 'bg-amber-400' : 'bg-gray-400'}`} />
              </span>

              <div className="rounded-lg border border-gray-200 bg-white p-4 hover:shadow-sm transition-shadow">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-gray-900">v{v.version_number}</span>
                      {v.is_original && (
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                          <Pin className="w-3 h-3" /> Gốc
                        </span>
                      )}
                      <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${meta.color}`}>
                        <Icon className="w-3 h-3" /> {meta.label}
                      </span>
                      {v.extractor_used && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded-full text-xs bg-gray-100 text-gray-600">
                          {v.extractor_used}
                        </span>
                      )}
                    </div>
                    <div className="mt-1 text-sm text-gray-600 truncate">{v.name}</div>
                    <div className="mt-2 flex items-center gap-4 text-xs text-gray-500">
                      <span>{formatTime(v.created_at)}</span>
                      <span>{formatBytes(v.file_size)}</span>
                      <span>{v.chunk_count} chunks</span>
                    </div>
                    {v.change_note && (
                      <div className="mt-2 text-xs text-gray-600 italic border-l-2 border-gray-200 pl-2">
                        {v.change_note}
                      </div>
                    )}
                  </div>

                  <div className="flex flex-col gap-1.5 flex-shrink-0">
                    <button
                      onClick={() => handleDownload(v)}
                      title="Tải file phiên bản này"
                      className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border border-gray-200 hover:bg-gray-50 text-gray-700"
                    >
                      <Download className="w-3.5 h-3.5" /> Tải về
                    </button>
                    {canRestore && (
                      <button
                        onClick={() => handleRestore(v)}
                        disabled={restoringId === v.id}
                        title="Khôi phục tài liệu về phiên bản này"
                        className="inline-flex items-center gap-1.5 px-2.5 py-1 text-xs rounded-md border border-blue-200 bg-blue-50 hover:bg-blue-100 text-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        {restoringId === v.id
                          ? <Loader2 className="w-3.5 h-3.5 animate-spin" />
                          : <RotateCcw className="w-3.5 h-3.5" />}
                        Khôi phục
                      </button>
                    )}
                  </div>
                </div>
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
