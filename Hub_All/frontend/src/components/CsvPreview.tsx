import { useEffect, useState } from 'react';
import { AlertCircle, Loader2 } from 'lucide-react';

interface Props {
  blob: Blob;
}

/** Render CSV qua PapaParse — auto-detect delimiter + encoding fallback (utf-8 → fallback).
 *  Dynamic import để KHÔNG bloat initial bundle (~45KB lib).
 *
 *  Quick task 2026-05-26-add-frontend-file-preview.
 */
export function CsvPreview({ blob }: Props) {
  const [rows, setRows] = useState<string[][]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);

    (async () => {
      try {
        const Papa = (await import('papaparse')).default;
        // Decode bytes → string với utf-8 ưu tiên, fallback latin-1 nếu BOM/non-utf8
        const buffer = await blob.arrayBuffer();
        let text: string;
        try {
          text = new TextDecoder('utf-8', { fatal: true }).decode(buffer);
        } catch {
          text = new TextDecoder('latin1').decode(buffer);
        }
        // Strip BOM nếu có (Excel Windows export hay có)
        if (text.charCodeAt(0) === 0xfeff) text = text.slice(1);

        const result = Papa.parse<string[]>(text, {
          delimiter: '', // auto-detect
          skipEmptyLines: true,
        });

        if (cancelled) return;
        if (result.errors.length > 0 && result.data.length === 0) {
          setError(result.errors[0].message);
          setLoading(false);
          return;
        }
        setRows(result.data as string[][]);
        setLoading(false);
      } catch (e) {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Không parse được file CSV');
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
        <p className="text-sm text-slate-500 dark:text-slate-400">Đang parse CSV…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <AlertCircle size={40} className="text-danger/60" />
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">Không parse được file CSV</p>
        <p className="text-xs text-slate-400 dark:text-slate-500 max-w-md text-center">{error}</p>
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full py-20 gap-3">
        <AlertCircle size={40} className="text-slate-400" />
        <p className="text-sm text-slate-500 dark:text-slate-400">File CSV trống</p>
      </div>
    );
  }

  const header = rows[0];
  const body = rows.slice(1);

  return (
    <div className="h-full overflow-auto p-4 bg-white dark:bg-slate-800">
      <table className="border-collapse w-full text-xs text-slate-800 dark:text-slate-100">
        <thead>
          <tr>
            {header.map((cell, i) => (
              <th
                key={i}
                className="border border-slate-300 dark:border-slate-600 px-2 py-1.5 bg-slate-100 dark:bg-slate-700 text-left font-semibold sticky top-0"
              >
                {cell}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {body.map((row, ri) => (
            <tr key={ri} className="hover:bg-slate-50 dark:hover:bg-slate-700/50">
              {row.map((cell, ci) => (
                <td key={ci} className="border border-slate-300 dark:border-slate-600 px-2 py-1 align-top">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="text-xs text-slate-400 dark:text-slate-500 mt-3">
        {body.length} hàng dữ liệu · {header.length} cột
      </p>
    </div>
  );
}
