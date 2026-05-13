import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import { X, Save, Eye, Code as CodeIcon, FileText, Loader2 } from 'lucide-react';
import { cn } from '../lib/utils';

interface Props {
  open: boolean;
  loading?: boolean;
  /** Tên file/tài liệu hiển thị trên header. */
  docName?: string;
  /** Nội dung markdown ban đầu. */
  initialContent: string;
  /** Trả về null = huỷ; trả về string = lưu nội dung mới. */
  onClose: (newContent: string | null) => void;
}

type Mode = 'edit' | 'split' | 'preview';

/**
 * Modal chỉnh sửa nội dung markdown của tài liệu — thay thế cho `window.prompt()`.
 *
 * 3 chế độ xem: chỉ editor / split editor+preview / chỉ preview.
 * Phím tắt: Esc huỷ, Ctrl/Cmd+S lưu.
 */
const EditContentModal: React.FC<Props> = ({ open, loading, docName, initialContent, onClose }) => {
  const [content, setContent] = useState(initialContent);
  const [mode, setMode] = useState<Mode>('split');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  // Reset state mỗi lần mở.
  useEffect(() => {
    if (open) {
      setContent(initialContent);
      setMode('split');
      // Auto focus textarea sau khi animate xong.
      setTimeout(() => textareaRef.current?.focus(), 150);
    }
  }, [open, initialContent]);

  // Phím tắt.
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose(null);
      } else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 's') {
        e.preventDefault();
        if (content !== initialContent) onClose(content);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, content, initialContent, onClose]);

  const charCount = content.length;
  const lineCount = useMemo(() => content.split('\n').length, [content]);
  const dirty = content !== initialContent;

  if (!open) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4"
        onClick={() => onClose(null)}
      >
        <motion.div
          initial={{ scale: 0.95, y: 20 }}
          animate={{ scale: 1, y: 0 }}
          exit={{ scale: 0.95, y: 20 }}
          transition={{ duration: 0.18 }}
          className="bg-white dark:bg-slate-800 rounded-xl shadow-2xl w-full max-w-6xl h-[85vh] flex flex-col overflow-hidden"
          onClick={(e) => e.stopPropagation()}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-700">
            <div className="flex items-center gap-2.5 min-w-0">
              <FileText size={18} className="text-brand-indigo flex-shrink-0" />
              <div className="min-w-0">
                <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100 truncate">
                  Sửa nội dung {docName && <span className="text-slate-500 font-normal">— {docName}</span>}
                </h2>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Chỉnh sửa markdown · sẽ chunk lại + re-embed sau khi xác nhận
                </p>
              </div>
            </div>
            <div className="flex items-center gap-1.5">
              {/* Mode switcher */}
              <div className="flex bg-slate-100 dark:bg-slate-900 rounded-lg p-0.5">
                <button
                  onClick={() => setMode('edit')}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md flex items-center gap-1 transition-colors',
                    mode === 'edit'
                      ? 'bg-white dark:bg-slate-700 text-brand-indigo shadow-sm'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-800',
                  )}
                  title="Chỉ editor"
                >
                  <CodeIcon size={13} /> Sửa
                </button>
                <button
                  onClick={() => setMode('split')}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md transition-colors',
                    mode === 'split'
                      ? 'bg-white dark:bg-slate-700 text-brand-indigo shadow-sm'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-800',
                  )}
                  title="Editor + Preview"
                >
                  Split
                </button>
                <button
                  onClick={() => setMode('preview')}
                  className={cn(
                    'px-2.5 py-1 text-xs rounded-md flex items-center gap-1 transition-colors',
                    mode === 'preview'
                      ? 'bg-white dark:bg-slate-700 text-brand-indigo shadow-sm'
                      : 'text-slate-600 dark:text-slate-300 hover:text-slate-800',
                  )}
                  title="Chỉ preview"
                >
                  <Eye size={13} /> Xem
                </button>
              </div>
              <button
                onClick={() => onClose(null)}
                className="p-1.5 text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:hover:bg-slate-700 rounded-md transition-colors"
                aria-label="Đóng"
              >
                <X size={18} />
              </button>
            </div>
          </div>

          {/* Body */}
          <div className="flex-1 flex min-h-0">
            {(mode === 'edit' || mode === 'split') && (
              <div className={cn('flex flex-col min-h-0', mode === 'split' ? 'w-1/2 border-r border-slate-200 dark:border-slate-700' : 'flex-1')}>
                <textarea
                  ref={textareaRef}
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  spellCheck={false}
                  className="flex-1 w-full p-4 text-sm font-mono leading-relaxed text-slate-800 dark:text-slate-100 bg-white dark:bg-slate-800 resize-none focus:outline-none"
                  placeholder="# Tiêu đề&#10;&#10;Nội dung markdown..."
                />
              </div>
            )}
            {(mode === 'preview' || mode === 'split') && (
              <div className={cn('overflow-auto p-5 bg-slate-50 dark:bg-slate-900', mode === 'split' ? 'w-1/2' : 'flex-1')}>
                <article className="prose prose-sm dark:prose-invert max-w-none prose-headings:scroll-mt-4">
                  <ReactMarkdown>{content || '*(trống)*'}</ReactMarkdown>
                </article>
              </div>
            )}
          </div>

          {/* Footer */}
          <div className="flex items-center justify-between px-5 py-3 border-t border-slate-200 dark:border-slate-700 bg-slate-50 dark:bg-slate-900/50">
            <div className="text-[11px] text-slate-500 dark:text-slate-400 flex items-center gap-3">
              <span>{lineCount.toLocaleString('vi-VN')} dòng · {charCount.toLocaleString('vi-VN')} ký tự</span>
              {dirty && <span className="text-amber-600 dark:text-amber-400">● đã thay đổi</span>}
              <span className="hidden md:inline text-slate-400">Esc · Hủy &nbsp;|&nbsp; Ctrl+S · Lưu</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={() => onClose(null)}
                disabled={loading}
                className="px-3.5 py-1.5 text-xs font-medium text-slate-700 dark:text-slate-200 bg-white dark:bg-slate-700 border border-slate-300 dark:border-slate-600 rounded-md hover:bg-slate-50 dark:hover:bg-slate-600 transition-colors disabled:opacity-50"
              >
                Hủy
              </button>
              <button
                onClick={() => onClose(content)}
                disabled={loading || !dirty}
                className="px-3.5 py-1.5 text-xs font-medium text-white bg-brand-indigo rounded-md hover:bg-brand-indigo/90 transition-colors flex items-center gap-1.5 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? <Loader2 size={13} className="animate-spin" /> : <Save size={13} />}
                Tiếp tục → Xem diff
              </button>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

export default EditContentModal;
