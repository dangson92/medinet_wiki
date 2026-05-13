import { useMemo, useState } from 'react';
import { diffLines, type Change } from 'diff';
import { X, AlertTriangle, FileText, Plus, Minus, Equal, Loader2, GitCompare, FileWarning } from 'lucide-react';
import type { DocumentDiffPreview, DocumentDiffMeta } from '../services/api';

interface Props {
  open: boolean;
  preview: DocumentDiffPreview | null;
  loading?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  /** Tiêu đề modal — VD: "Tải lại file" hoặc "Sửa nội dung". */
  title: string;
  /** Nhãn nút xác nhận — VD: "Xác nhận tải lên & vector hóa". */
  confirmLabel?: string;
  /** Đang chạy action confirm (disable nút). */
  confirming?: boolean;
}

function formatBytes(n: number): string {
  if (n >= 1048576) return (n / 1048576).toFixed(1) + ' MB';
  if (n >= 1024) return (n / 1024).toFixed(0) + ' KB';
  return n + ' B';
}

interface DiffStats {
  added: number;
  removed: number;
  unchanged: number;
}

function computeStats(parts: Change[]): DiffStats {
  let added = 0, removed = 0, unchanged = 0;
  for (const p of parts) {
    const lines = (p.value.match(/\n/g)?.length ?? 0) + (p.value.endsWith('\n') ? 0 : 1);
    if (p.added) added += lines;
    else if (p.removed) removed += lines;
    else unchanged += lines;
  }
  return { added, removed, unchanged };
}

function MetaRow({ label, oldVal, newVal }: { label: string; oldVal: string; newVal: string }) {
  const changed = oldVal !== newVal;
  return (
    <div className="grid grid-cols-3 gap-2 py-1.5 text-xs border-b border-slate-100 dark:border-slate-700">
      <div className="text-slate-500 dark:text-slate-400">{label}</div>
      <div className={`font-mono truncate ${changed ? 'text-red-600 line-through' : 'text-slate-700 dark:text-slate-200'}`}>{oldVal}</div>
      <div className={`font-mono truncate ${changed ? 'text-green-700 dark:text-green-400 font-semibold' : 'text-slate-700 dark:text-slate-200'}`}>{newVal}</div>
    </div>
  );
}

function BinaryDiff({ oldMeta, newMeta, note }: { oldMeta?: DocumentDiffMeta; newMeta?: DocumentDiffMeta; note?: string }) {
  return (
    <div className="space-y-3">
      <div className="flex items-start gap-2 p-3 rounded-lg bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800/40 text-amber-800 dark:text-amber-300 text-xs">
        <FileWarning className="w-4 h-4 flex-shrink-0 mt-0.5" />
        <div>
          <div className="font-medium">Không thể preview nội dung file binary</div>
          <div className="opacity-80 mt-0.5">{note || 'Hệ thống chỉ hiển thị metadata. Vector hóa sẽ chạy lại sau khi xác nhận.'}</div>
        </div>
      </div>

      {oldMeta && newMeta && (
        <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden">
          <div className="grid grid-cols-3 gap-2 px-3 py-2 bg-slate-50 dark:bg-slate-800 text-xs font-semibold text-slate-600 dark:text-slate-300">
            <div></div>
            <div>Phiên bản hiện tại</div>
            <div>Phiên bản mới</div>
          </div>
          <div className="px-3">
            <MetaRow label="Tên file" oldVal={oldMeta.name} newVal={newMeta.name} />
            <MetaRow label="Định dạng" oldVal={oldMeta.file_type.toUpperCase()} newVal={newMeta.file_type.toUpperCase()} />
            <MetaRow label="Kích thước" oldVal={formatBytes(oldMeta.file_size)} newVal={formatBytes(newMeta.file_size)} />
            <MetaRow
              label="SHA-256"
              oldVal={oldMeta.file_hash ? oldMeta.file_hash.slice(0, 16) + '…' : '(không tính được)'}
              newVal={newMeta.file_hash.slice(0, 16) + '…'}
            />
          </div>
        </div>
      )}
    </div>
  );
}

function TextDiff({ oldText, newText }: { oldText: string; newText: string }) {
  const parts = useMemo(() => diffLines(oldText, newText), [oldText, newText]);
  const stats = useMemo(() => computeStats(parts), [parts]);
  const noChange = stats.added === 0 && stats.removed === 0;

  if (noChange) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-slate-500 dark:text-slate-400">
        <Equal className="w-8 h-8 mb-2 opacity-40" />
        <p className="text-sm">Không có thay đổi nội dung. Hai phiên bản giống hệt nhau.</p>
      </div>
    );
  }

  // Build unified diff hiển thị từng dòng có prefix +/- và màu nền.
  const linesOut: { kind: 'add' | 'del' | 'eq'; text: string; oldLn?: number; newLn?: number }[] = [];
  let oldLn = 1, newLn = 1;
  for (const p of parts) {
    const segLines = p.value.split('\n');
    // Bỏ dòng trống cuối nếu chuỗi kết thúc bằng \n.
    if (segLines.length > 0 && segLines[segLines.length - 1] === '') segLines.pop();
    for (const ln of segLines) {
      if (p.added) linesOut.push({ kind: 'add', text: ln, newLn: newLn++ });
      else if (p.removed) linesOut.push({ kind: 'del', text: ln, oldLn: oldLn++ });
      else { linesOut.push({ kind: 'eq', text: ln, oldLn: oldLn++, newLn: newLn++ }); }
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-3 text-xs">
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 font-medium">
          <Plus className="w-3 h-3" /> {stats.added} dòng thêm
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 font-medium">
          <Minus className="w-3 h-3" /> {stats.removed} dòng xóa
        </span>
        <span className="inline-flex items-center gap-1 px-2 py-1 rounded-md bg-slate-100 dark:bg-slate-700 text-slate-600 dark:text-slate-300">
          {stats.unchanged} dòng giữ nguyên
        </span>
      </div>

      <div className="rounded-lg border border-slate-200 dark:border-slate-700 overflow-hidden font-mono text-xs">
        <div className="max-h-[55vh] overflow-auto bg-white dark:bg-slate-900">
          {linesOut.map((l, i) => {
            const bg = l.kind === 'add'
              ? 'bg-green-50 dark:bg-green-900/20'
              : l.kind === 'del'
                ? 'bg-red-50 dark:bg-red-900/20'
                : '';
            const textColor = l.kind === 'add'
              ? 'text-green-900 dark:text-green-300'
              : l.kind === 'del'
                ? 'text-red-900 dark:text-red-300'
                : 'text-slate-700 dark:text-slate-300';
            const prefix = l.kind === 'add' ? '+' : l.kind === 'del' ? '-' : ' ';
            return (
              <div key={i} className={`flex ${bg}`}>
                <span className="px-2 py-0.5 select-none text-slate-400 dark:text-slate-500 text-right border-r border-slate-200 dark:border-slate-700 w-12 flex-shrink-0">
                  {l.oldLn ?? ''}
                </span>
                <span className="px-2 py-0.5 select-none text-slate-400 dark:text-slate-500 text-right border-r border-slate-200 dark:border-slate-700 w-12 flex-shrink-0">
                  {l.newLn ?? ''}
                </span>
                <span className={`px-2 py-0.5 select-none w-6 flex-shrink-0 ${textColor}`}>{prefix}</span>
                <span className={`px-2 py-0.5 whitespace-pre-wrap break-all ${textColor}`}>{l.text || ' '}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

export default function DocumentDiffPreview({
  open, preview, loading, onConfirm, onCancel,
  title, confirmLabel = 'Xác nhận tải lên & vector hóa', confirming,
}: Props) {
  const [acknowledged, setAcknowledged] = useState(false);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm"
      onClick={confirming ? undefined : onCancel}
    >
      <div
        className="bg-white dark:bg-slate-900 rounded-2xl shadow-2xl w-full max-w-5xl max-h-[92vh] flex flex-col overflow-hidden"
        onClick={e => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-4 border-b border-slate-100 dark:border-slate-700 shrink-0">
          <div className="flex items-center gap-2 min-w-0">
            <GitCompare className="w-5 h-5 text-accent flex-shrink-0" />
            <h3 className="text-sm font-semibold text-slate-900 dark:text-white truncate">{title}</h3>
            <span className="text-xs text-slate-400">— xem khác biệt trước khi xác nhận</span>
          </div>
          <button
            onClick={onCancel}
            disabled={confirming}
            className="p-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-colors disabled:opacity-50"
          >
            <X size={18} />
          </button>
        </div>

        <div className="flex-1 overflow-auto p-5">
          {loading && (
            <div className="flex flex-col items-center justify-center py-16 gap-3 text-slate-500">
              <Loader2 size={28} className="animate-spin text-accent" />
              <p className="text-sm">Đang trích xuất nội dung để so sánh…</p>
            </div>
          )}

          {!loading && preview && preview.is_text && (
            <TextDiff oldText={preview.old_text || ''} newText={preview.new_text || ''} />
          )}

          {!loading && preview && !preview.is_text && (
            <BinaryDiff oldMeta={preview.old_meta} newMeta={preview.new_meta} note={preview.note} />
          )}

          {!loading && !preview && (
            <div className="flex flex-col items-center justify-center py-16 gap-2 text-red-600">
              <AlertTriangle className="w-6 h-6" />
              <p className="text-sm">Không lấy được dữ liệu preview</p>
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-5 py-3 border-t border-slate-100 dark:border-slate-700 shrink-0 bg-slate-50 dark:bg-slate-800/50">
          <label className="flex items-center gap-2 text-xs text-slate-600 dark:text-slate-300 cursor-pointer">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={e => setAcknowledged(e.target.checked)}
              className="rounded border-slate-300"
            />
            <span>Tôi đã xem khác biệt và xác nhận tiếp tục vector hóa</span>
          </label>
          <div className="flex items-center gap-2">
            <button
              onClick={onCancel}
              disabled={confirming}
              className="px-3 py-1.5 text-xs font-medium rounded-lg border border-slate-200 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 disabled:opacity-50"
            >
              Hủy
            </button>
            <button
              onClick={onConfirm}
              disabled={!acknowledged || loading || confirming || !preview}
              className="inline-flex items-center gap-2 px-3 py-1.5 text-xs font-medium rounded-lg bg-accent hover:bg-accent/90 text-white disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {confirming ? <Loader2 size={14} className="animate-spin" /> : <FileText size={14} />}
              {confirmLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
