import { useEffect, useRef, useState } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';

interface Props {
  blob: Blob;
}

/** Render DOCX trực tiếp trong browser qua `docx-preview` (dynamic import — KHÔNG bloat
 *  initial bundle). Mount vào div container, renderAsync convert XML → HTML.
 *
 *  Quick task 2026-05-26-add-frontend-file-preview.
 */
export function DocxPreview({ blob }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const { renderAsync } = await import('docx-preview');
        if (cancelled || !containerRef.current) return;
        containerRef.current.innerHTML = '';
        await renderAsync(blob, containerRef.current, undefined, {
          className: 'docx-preview-doc',
          inWrapper: true,
          ignoreWidth: false,
          ignoreHeight: false,
          ignoreFonts: false,
          breakPages: true,
          experimental: false,
          trimXmlDeclaration: true,
          useBase64URL: false,
        });
        if (!cancelled) setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Không render được file DOCX');
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [blob]);

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <AlertCircle size={40} className="text-danger/60" />
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Không render được file DOCX</p>
        <p className="text-xs text-slate-400 dark:text-slate-500 max-w-md text-center">{error}</p>
      </div>
    );
  }

  return (
    <div className="relative w-full h-full overflow-auto bg-slate-100 dark:bg-slate-900 p-4">
      {loading && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 z-10 bg-slate-100/80 dark:bg-slate-900/80">
          <Loader2 size={32} className="animate-spin text-accent" />
          <p className="text-sm text-slate-500 dark:text-slate-400">Đang render DOCX…</p>
        </div>
      )}
      <div ref={containerRef} className="docx-preview-container max-w-4xl mx-auto bg-white dark:bg-white shadow-lg rounded-lg" />
    </div>
  );
}
