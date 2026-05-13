import React, { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { X, BookOpen } from 'lucide-react';
import type { CitationRefAPI } from '../services/api';

type Props = {
  text: string;
  citations?: CitationRefAPI[];
  /** Called when user wants to open the source document (optional). */
  onOpenSource?: (c: CitationRefAPI) => void;
};

type Token =
  | { kind: 'text'; value: string }
  | { kind: 'cite'; marker: string; citation: CitationRefAPI };

const MARKER_RE = /\[src:([^\]\s]+)\]/g;

/**
 * CitationText renders an LLM answer that contains `[src:<id>]` markers by
 * replacing each marker with a numbered superscript chip. Hovering a chip
 * shows the source snippet; clicking opens a detail panel.
 *
 * If no citations are provided (or none match), it renders the raw text
 * (markers passed through) — safe for backwards compatibility with the
 * previous answer renderer.
 */
const CitationText: React.FC<Props> = ({ text, citations, onOpenSource }) => {
  const byID = useMemo(() => {
    const m = new Map<string, CitationRefAPI>();
    (citations || []).forEach((c) => m.set(c.id, c));
    return m;
  }, [citations]);

  const tokens = useMemo<Token[]>(() => {
    if (!text) return [];
    if (byID.size === 0) return [{ kind: 'text', value: text }];
    const out: Token[] = [];
    let lastIdx = 0;
    MARKER_RE.lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = MARKER_RE.exec(text)) !== null) {
      const [full, id] = match;
      const start = match.index;
      if (start > lastIdx) out.push({ kind: 'text', value: text.slice(lastIdx, start) });
      const cite = byID.get(id);
      if (cite) {
        out.push({ kind: 'cite', marker: full, citation: cite });
      } else {
        // Unknown id — leave marker as-is so nothing is silently dropped.
        out.push({ kind: 'text', value: full });
      }
      lastIdx = start + full.length;
    }
    if (lastIdx < text.length) out.push({ kind: 'text', value: text.slice(lastIdx) });
    return out;
  }, [text, byID]);

  const [active, setActive] = useState<CitationRefAPI | null>(null);

  const orderedCitations = useMemo(() => {
    // De-duplicate and order by first appearance in `tokens`.
    const seen = new Set<string>();
    const out: CitationRefAPI[] = [];
    for (const t of tokens) {
      if (t.kind !== 'cite') continue;
      if (seen.has(t.citation.id)) continue;
      seen.add(t.citation.id);
      out.push(t.citation);
    }
    return out;
  }, [tokens]);

  return (
    <div className="space-y-3">
      <div className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-line">
        {tokens.map((t, i) =>
          t.kind === 'text' ? (
            <span key={i}>{t.value}</span>
          ) : (
            <CitationChip
              key={i}
              number={t.citation.number}
              citation={t.citation}
              onClick={() => setActive(t.citation)}
            />
          )
        )}
      </div>

      {orderedCitations.length > 0 && (
        <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-100 dark:border-slate-800">
          <span className="text-[10px] uppercase tracking-wider text-slate-400 font-semibold pt-1">
            Trích dẫn:
          </span>
          {orderedCitations.map((c) => (
            <button
              key={c.id}
              type="button"
              onClick={() => setActive(c)}
              className="text-[11px] px-2 py-1 rounded-md bg-accent/10 hover:bg-accent/20 text-accent border border-accent/20 transition-colors max-w-xs truncate"
              title={c.snippet}
            >
              [{c.number}] {c.document_name}
            </button>
          ))}
        </div>
      )}

      <AnimatePresence>
        {active && (
          <CitationDetail
            citation={active}
            onClose={() => setActive(null)}
            onOpenSource={onOpenSource}
          />
        )}
      </AnimatePresence>
    </div>
  );
};

const CitationChip: React.FC<{
  number: number;
  citation: CitationRefAPI;
  onClick: () => void;
}> = ({ number, citation, onClick }) => (
  <button
    type="button"
    onClick={onClick}
    title={`${citation.document_name} — match ${Math.round(citation.score * 100)}%`}
    className="inline-flex items-center align-super text-[10px] font-bold leading-none px-1.5 py-0.5 mx-0.5 rounded-md bg-accent/15 hover:bg-accent/30 text-accent transition-colors cursor-pointer select-none"
  >
    [{number}]
  </button>
);

const CitationDetail: React.FC<{
  citation: CitationRefAPI;
  onClose: () => void;
  onOpenSource?: (c: CitationRefAPI) => void;
}> = ({ citation, onClose, onOpenSource }) => (
  <motion.div
    initial={{ opacity: 0, y: 6 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: 6 }}
    className="mt-2 rounded-lg border border-accent/20 bg-white dark:bg-slate-900 shadow-sm p-3 text-sm"
  >
    <div className="flex items-start justify-between gap-2 mb-2">
      <div className="flex items-center gap-2 min-w-0">
        <span className="text-[10px] font-bold text-accent bg-accent/10 px-1.5 py-0.5 rounded shrink-0">
          [{citation.number}]
        </span>
        <div className="min-w-0">
          <p className="text-xs font-semibold text-slate-800 dark:text-slate-100 truncate">
            {citation.document_name}
          </p>
          <p className="text-[10px] text-slate-400">
            {citation.hub_name} · chunk #{citation.chunk_index} · match{' '}
            {Math.round(citation.score * 100)}%
          </p>
        </div>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="shrink-0 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
        aria-label="Đóng"
      >
        <X size={14} />
      </button>
    </div>
    <p className="text-xs text-slate-600 dark:text-slate-300 leading-relaxed whitespace-pre-line">
      {citation.snippet}
    </p>
    {onOpenSource && (
      <button
        type="button"
        onClick={() => onOpenSource(citation)}
        className="mt-2 inline-flex items-center gap-1 text-[11px] text-accent hover:underline"
      >
        <BookOpen size={12} />
        Mở tài liệu
      </button>
    )}
  </motion.div>
);

export default CitationText;
