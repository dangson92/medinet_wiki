import { useEffect, useState } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';

interface Props {
  blob: Blob;
}

interface SheetData {
  name: string;
  html: string;
}

/** Render XLSX qua SheetJS (xlsx) — parse blob → mỗi sheet thành HTML table.
 *  Dynamic import để KHÔNG bloat initial bundle (~300KB lib).
 *
 *  Quick task 2026-05-26-add-frontend-file-preview.
 */
export function XlsxPreview({ blob }: Props) {
  const [sheets, setSheets] = useState<SheetData[]>([]);
  const [activeIdx, setActiveIdx] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const XLSX = await import('xlsx');
        const buffer = await blob.arrayBuffer();
        if (cancelled) return;
        const workbook = XLSX.read(buffer, { type: 'array' });
        const result: SheetData[] = workbook.SheetNames.map((name) => ({
          name,
          html: XLSX.utils.sheet_to_html(workbook.Sheets[name], { editable: false }),
        }));
        if (!cancelled) {
          setSheets(result);
          setLoading(false);
        }
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Không render được file XLSX');
          setLoading(false);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [blob]);

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <Loader2 size={32} className="animate-spin text-accent" />
        <p className="text-sm text-slate-500 dark:text-slate-400">Đang render XLSX…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <AlertCircle size={40} className="text-danger/60" />
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Không render được file XLSX</p>
        <p className="text-xs text-slate-400 dark:text-slate-500 max-w-md text-center">{error}</p>
      </div>
    );
  }

  if (sheets.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <AlertCircle size={40} className="text-slate-400" />
        <p className="text-sm text-slate-500 dark:text-slate-400">File XLSX không có sheet nào</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-white dark:bg-slate-800">
      {sheets.length > 1 && (
        <div className="flex items-center gap-1 px-4 py-2 border-b border-slate-200 dark:border-slate-700 overflow-x-auto shrink-0">
          {sheets.map((s, i) => (
            <button
              key={s.name + i}
              onClick={() => setActiveIdx(i)}
              className={
                i === activeIdx
                  ? 'px-3 py-1.5 text-xs font-medium rounded-lg bg-accent text-white whitespace-nowrap'
                  : 'px-3 py-1.5 text-xs font-medium rounded-lg text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700 whitespace-nowrap'
              }
            >
              {s.name}
            </button>
          ))}
        </div>
      )}
      <div className="flex-1 overflow-auto p-4">
        <div
          className="xlsx-preview-sheet text-xs text-slate-800 dark:text-slate-100 [&_table]:border-collapse [&_table]:w-full [&_td]:border [&_td]:border-slate-300 [&_td]:dark:border-slate-600 [&_td]:px-2 [&_td]:py-1 [&_th]:border [&_th]:border-slate-300 [&_th]:dark:border-slate-600 [&_th]:px-2 [&_th]:py-1 [&_th]:bg-slate-100 [&_th]:dark:bg-slate-700"
          dangerouslySetInnerHTML={{ __html: sheets[activeIdx].html }}
        />
      </div>
    </div>
  );
}
