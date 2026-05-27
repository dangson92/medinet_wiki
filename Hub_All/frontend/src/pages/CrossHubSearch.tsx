import React, { useState, useEffect, useRef, useMemo } from 'react';
import { api, type HubAPI, type SearchResultAPI, type SearchAnswerAPI } from '../services/api';
import { cn } from '../lib/utils';
import {
  Search,
  Filter,
  Loader2,
  Sparkles,
  Send,
  BookOpen,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Check,
  Share2,
  RefreshCw,
  Paperclip,
  Image as ImageIcon,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import CitationText from '../components/CitationText';
import FileTypeIcon from '../components/FileTypeIcon';
import { useAuth } from '../contexts/AuthContext';

/** Một lượt hỏi-đáp trong hội thoại. */
interface ChatTurn {
  id: string;
  question: string;
  askedAt: Date;
  answer: SearchAnswerAPI | null;
  answeredAt: Date | null;
  error?: string;
  feedback?: 'up' | 'down';
}

const KB_PREVIEW = 4;

const QUICK_TOPICS = [
  'Quy trình nghiệp vụ',
  'Hướng dẫn sử dụng',
  'Văn bản - Quy định',
  'Biểu mẫu - Mẫu đơn',
];

const formatScore = (score: number) => Math.round(score * 100);

const formatClock = (d: Date) =>
  d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });

const CrossHubSearch = () => {
  const { user } = useAuth();
  const userInitial = (user?.user.name || 'U').charAt(0).toUpperCase();

  const [input, setInput] = useState('');
  const [isAsking, setIsAsking] = useState(false);
  const [turns, setTurns] = useState<ChatTurn[]>([]);

  // Tri thức trích xuất từ lượt hỏi gần nhất
  const [knowledge, setKnowledge] = useState<SearchResultAPI[]>([]);
  const [kbFilter, setKbFilter] = useState('');
  const [kbExpanded, setKbExpanded] = useState(false);
  const [expandedKbId, setExpandedKbId] = useState<string | null>(null);

  // Bộ lọc Hub
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [selectedHubId, setSelectedHubId] = useState('');
  const [hubMenuOpen, setHubMenuOpen] = useState(false);

  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api.getHubs().then((res) => {
      if (res.success && res.data) {
        setHubs(res.data.filter((h) => h.status === 'active'));
      }
    });
  }, []);

  // Cuộn xuống cuối khi có lượt mới hoặc trạng thái trả lời thay đổi
  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [turns, isAsking]);

  const handleAsk = async (raw?: string) => {
    const question = (raw ?? input).trim();
    if (!question || isAsking) return;

    setInput('');
    setIsAsking(true);

    const turnId = `${Date.now()}`;
    const turn: ChatTurn = {
      id: turnId,
      question,
      askedAt: new Date(),
      answer: null,
      answeredAt: null,
    };
    setTurns((prev) => [...prev, turn]);

    const finish = (patch: Partial<ChatTurn>) =>
      setTurns((prev) =>
        prev.map((t) => (t.id === turnId ? { ...t, ...patch, answeredAt: new Date() } : t)),
      );

    try {
      const hubIds = selectedHubId ? [selectedHubId] : [];
      const answerRes = await api.searchAnswer({ query: question, hub_ids: hubIds, top_k: 5 });

      if (answerRes.success && answerRes.data) {
        finish({ answer: answerRes.data });
        setKnowledge(answerRes.data.search_results || []);
        setKbExpanded(false);
      } else {
        // RAG answer lỗi — fallback sang search thường để vẫn có tri thức
        const res = await api.crossHubSearch({ query: question, hub_ids: hubIds, top_k: 20 });
        if (res.success && res.data) {
          setKnowledge(res.data.results || []);
          setKbExpanded(false);
        }
        finish({ error: 'Không tạo được câu trả lời từ AI. Xem tri thức liên quan ở cột bên trái.' });
      }
    } catch {
      finish({ error: 'Không thể kết nối tới server. Vui lòng thử lại.' });
    } finally {
      setIsAsking(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleAsk();
    }
  };

  const setFeedback = (turnId: string, fb: 'up' | 'down') =>
    setTurns((prev) =>
      prev.map((t) => (t.id === turnId ? { ...t, feedback: t.feedback === fb ? undefined : fb } : t)),
    );

  const filteredKnowledge = useMemo(() => {
    const q = kbFilter.trim().toLowerCase();
    if (!q) return knowledge;
    return knowledge.filter(
      (k) =>
        k.title.toLowerCase().includes(q) ||
        k.snippet.toLowerCase().includes(q) ||
        k.hub_name.toLowerCase().includes(q),
    );
  }, [knowledge, kbFilter]);

  const visibleKnowledge = kbExpanded ? filteredKnowledge : filteredKnowledge.slice(0, KB_PREVIEW);
  // Lấy answer mới nhất (turn cuối có answer) — KHÔNG dùng findLast() vì cần ES2023.
  const lastAnswer = useMemo(() => {
    for (let i = turns.length - 1; i >= 0; i--) {
      if (turns[i].answer) return turns[i].answer;
    }
    return null;
  }, [turns]);

  return (
    // Cố định chiều cao theo viewport — chỉ scroll trong khung chat, KHÔNG scroll trang.
    // calc: 100dvh - header (64px) - main padding top+bottom (48px lg:p-6) - footer (~48px) ≈ 10rem.
    <div className="flex gap-6 h-[calc(100dvh-10rem)] min-h-[500px]">
      {/* ─── Cột trái: Tri thức đã trích xuất — mẫu giao-dien-mau hoi_dap_ai §"Knowledge Source Panel" ─── */}
      <aside className="hidden lg:flex w-80 shrink-0 flex-col m3-card overflow-hidden">
        <div className="p-4 border-b border-outline-variant flex items-center justify-between">
          <h2 className="text-body-lg font-bold text-on-surface dark:text-white">Tri thức đã trích xuất</h2>
          <div className="relative">
            <button
              onClick={() => setHubMenuOpen((v) => !v)}
              className={cn(
                'p-1 rounded-md transition-colors',
                selectedHubId
                  ? 'bg-primary/10 text-primary'
                  : 'text-outline hover:bg-surface-container',
              )}
              title="Lọc theo Hub"
            >
              <Filter size={20} />
            </button>
            <AnimatePresence>
              {hubMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setHubMenuOpen(false)} />
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -6 }}
                    className="absolute right-0 mt-2 w-56 bg-white border border-outline-variant rounded-lg shadow-xl z-50 overflow-hidden p-1.5 dark:bg-slate-800 dark:border-slate-700"
                  >
                    <p className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-outline">
                      Phạm vi tìm kiếm
                    </p>
                    {[{ id: '', name: 'Tất cả Hub' }, ...hubs].map((h) => (
                      <button
                        key={h.id || 'all'}
                        onClick={() => {
                          setSelectedHubId(h.id);
                          setHubMenuOpen(false);
                        }}
                        className={cn(
                          'w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-body-sm transition-colors',
                          selectedHubId === h.id
                            ? 'bg-primary/10 text-primary font-semibold'
                            : 'text-on-surface hover:bg-surface-container-low dark:text-slate-200 dark:hover:bg-slate-700',
                        )}
                      >
                        <span className="truncate">{h.name}</span>
                        {selectedHubId === h.id && <Check size={14} className="shrink-0" />}
                      </button>
                    ))}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Ô tìm kiếm tri thức */}
        <div className="p-3 border-b border-outline-variant">
          <div className="relative">
            <Search size={18} className="absolute left-3 top-1/2 -translate-y-1/2 text-outline pointer-events-none" />
            <input
              type="text"
              value={kbFilter}
              onChange={(e) => setKbFilter(e.target.value)}
              placeholder="Tìm kiếm tri thức..."
              className="w-full bg-surface-container-low border-none rounded-lg py-1.5 pl-9 pr-3 text-body-sm focus:ring-2 focus:ring-primary/20 outline-none dark:bg-slate-700 dark:text-white"
            />
          </div>
        </div>

        {/* Danh sách thẻ tri thức */}
        <div className="flex-1 overflow-y-auto p-3 space-y-3">
          {knowledge.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 text-on-surface-variant">
              <BookOpen size={36} className="opacity-30 mb-3" />
              <p className="text-body-sm font-medium">Chưa có tri thức</p>
              <p className="text-[11px] mt-1">Đặt câu hỏi để hệ thống trích xuất tri thức liên quan.</p>
            </div>
          ) : filteredKnowledge.length === 0 ? (
            <p className="text-body-sm text-on-surface-variant text-center py-8">
              Không có tri thức khớp "{kbFilter}".
            </p>
          ) : (
            <>
              {visibleKnowledge.map((k) => (
                <button
                  key={k.id}
                  onClick={() => setExpandedKbId(expandedKbId === k.id ? null : k.id)}
                  className="w-full text-left p-3 rounded-lg border border-outline-variant bg-white hover:border-primary/40 hover:bg-primary/5 transition-all group dark:bg-slate-800 dark:border-slate-700"
                >
                  <div className="flex items-center gap-2 mb-2">
                    <span className="px-2 py-0.5 bg-primary text-on-primary text-[10px] rounded font-bold truncate max-w-full">
                      {k.hub_name}
                    </span>
                  </div>
                  <h3 className="text-body-sm font-bold mb-1 group-hover:text-primary transition-colors flex items-center gap-1.5 text-on-surface dark:text-white">
                    <FileTypeIcon fileName={k.title} size={18} className="shrink-0" />
                    <span className="truncate">{k.title}</span>
                  </h3>
                  <p
                    className={cn(
                      'text-[11px] text-on-surface-variant leading-relaxed',
                      expandedKbId === k.id ? 'whitespace-pre-line' : 'line-clamp-2',
                    )}
                  >
                    {(k.content || k.snippet).replace(/^#{1,4}\s+/gm, '').replace(/\*\*/g, '')}
                  </p>
                  {/* Progress bar + score % */}
                  <div className="mt-2 flex items-center gap-2">
                    <div className="flex-1 h-1 bg-surface-container-highest rounded-full overflow-hidden">
                      <div
                        className="h-full bg-primary"
                        style={{ width: `${formatScore(k.score)}%` }}
                      />
                    </div>
                    <span className="text-[10px] font-bold text-primary tabular-nums shrink-0">
                      {formatScore(k.score)}%
                    </span>
                  </div>
                </button>
              ))}
            </>
          )}
        </div>

        {filteredKnowledge.length > KB_PREVIEW && (
          <button
            onClick={() => setKbExpanded((v) => !v)}
            className="p-4 text-body-sm text-outline font-semibold hover:text-primary transition-colors flex items-center justify-center gap-1 border-t border-outline-variant"
          >
            {kbExpanded ? (
              <>
                Thu gọn <ChevronUp size={16} />
              </>
            ) : (
              <>
                Xem thêm ({filteredKnowledge.length - KB_PREVIEW}) <ChevronDown size={16} />
              </>
            )}
          </button>
        )}
      </aside>

      {/* ─── Cột phải: Chat workspace — mẫu giao-dien-mau hoi_dap_ai §"Chat Workspace" ─── */}
      <section className="flex-1 flex flex-col min-w-0 m3-card overflow-hidden">
        {/* Chat header */}
        <div className="px-6 py-4 flex items-center justify-between border-b border-outline-variant shrink-0">
          <div className="flex items-center gap-3 min-w-0">
            <div className="w-10 h-10 flex items-center justify-center shrink-0">
              <img src="/mascot.png" alt="AI Mascot" className="w-10 h-10 object-contain" />
            </div>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="text-body-md font-bold text-on-surface dark:text-white truncate">Hỏi đáp với Tri thức</h3>
                {lastAnswer && (
                  <span className="text-[10px] bg-primary-fixed text-on-primary-fixed-variant px-1.5 py-0.5 rounded font-bold uppercase">
                    {lastAnswer.model}
                  </span>
                )}
              </div>
              <p className="text-[10px] text-on-surface-variant">Phản hồi dựa trên cơ sở dữ liệu nội bộ</p>
            </div>
          </div>
          <div className="flex gap-1 shrink-0">
            <button className="p-2 hover:bg-surface-container rounded-lg transition-colors text-outline" title="Chia sẻ">
              <Share2 size={20} />
            </button>
            <button
              onClick={() => { setTurns([]); setKnowledge([]); }}
              className="p-2 hover:bg-surface-container rounded-lg transition-colors text-outline"
              title="Bắt đầu hội thoại mới"
            >
              <RefreshCw size={20} />
            </button>
          </div>
        </div>

        {/* Message area */}
        <div ref={scrollRef} className="flex-1 overflow-y-auto p-6 lg:p-8 space-y-8 scroll-smooth bg-surface">
          {/* Empty state — chỉ hiện khi chưa có hội thoại */}
          {turns.length === 0 && (
            <div className="max-w-2xl mx-auto text-center py-12">
              <div className="w-20 h-20 mx-auto flex items-center justify-center mb-4">
                <img src="/mascot.png" alt="AI Mascot" className="w-20 h-20 object-contain" />
              </div>
              <h2 className="font-display text-headline-md text-on-surface dark:text-white mb-2">
                Xin chào! Hỏi tôi bất cứ điều gì
              </h2>
              <p className="text-body-md text-on-surface-variant">
                Trợ lý Medinet Wiki sẽ trả lời dựa trên cơ sở dữ liệu nội bộ — có trích dẫn nguồn rõ ràng.
              </p>
            </div>
          )}

          {/* Hội thoại */}
          {turns.map((turn) => (
            <React.Fragment key={turn.id}>
              {/* User message — bubble bg-secondary-container, rounded-tr-none, avatar right */}
              <div className="flex gap-4 flex-row-reverse">
                <div className="shrink-0">
                  <div className="w-10 h-10 rounded-full bg-secondary text-on-secondary flex items-center justify-center font-bold text-xs shadow-sm">
                    {userInitial}
                  </div>
                </div>
                <div className="flex-1 flex flex-col items-end min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <span className="text-[10px] text-outline">{formatClock(turn.askedAt)}</span>
                    <span className="text-label-md font-bold text-secondary">Bạn</span>
                  </div>
                  <div className="bg-secondary-container text-on-secondary-container px-4 py-2.5 rounded-2xl rounded-tr-none text-body-md shadow-sm max-w-full whitespace-pre-line">
                    {turn.question}
                  </div>
                </div>
              </div>

              {/* AI message — card bg-white border, avatar left */}
              <div className="flex gap-4">
                <div className="shrink-0">
                  <div className="w-10 h-10 flex items-center justify-center shrink-0">
                    <img src="/mascot.png" alt="AI Mascot" className="w-10 h-10 object-contain" />
                  </div>
                </div>
                <div className="flex-1 min-w-0">
                  {!turn.answer && !turn.error ? (
                    <div className="bg-white border border-outline-variant rounded-2xl p-4 inline-flex items-center gap-2 text-body-sm text-on-surface-variant dark:bg-slate-800 dark:border-slate-700">
                      <Loader2 size={16} className="animate-spin text-primary" />
                      Đang soạn câu trả lời...
                    </div>
                  ) : turn.error ? (
                    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-2xl rounded-tl-none p-4 flex items-start gap-2.5">
                      <AlertTriangle size={16} className="text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-body-sm text-amber-700 dark:text-amber-300 font-medium leading-relaxed">
                        {turn.error}
                      </p>
                    </div>
                  ) : (
                    <div className="bg-white border border-outline-variant/40 rounded-2xl p-4 dark:bg-slate-800 dark:border-slate-700">
                      <div className="flex items-center justify-between mb-2">
                        <span className="text-label-md font-bold text-primary">{turn.answer!.model}</span>
                        <span className="text-[10px] text-outline">
                          {turn.answeredAt ? formatClock(turn.answeredAt) : ''} ·{' '}
                          {(turn.answer!.query_time_ms / 1000).toFixed(1)}s
                        </span>
                      </div>

                      <div className="text-body-md leading-relaxed text-on-surface dark:text-white">
                        <CitationText text={turn.answer!.answer} citations={turn.answer!.citations} />
                      </div>

                      {/* Citations chips */}
                      {turn.answer!.citations && turn.answer!.citations.length > 0 && (
                        <div className="mt-6 pt-4 border-t border-outline-variant">
                          <div className="flex items-center gap-2 mb-3">
                            <span className="material-symbols-outlined text-[16px] text-primary" aria-hidden>🔗</span>
                            <span className="text-[11px] font-bold text-outline uppercase tracking-wider">
                              Trích dẫn
                            </span>
                          </div>
                          <div className="flex flex-wrap gap-2">
                            {turn.answer!.citations.map((c, i) => (
                              <span
                                key={i}
                                className="px-3 py-1 bg-surface-container-low border border-outline-variant rounded-full text-[11px] text-primary font-medium cursor-pointer hover:bg-primary-fixed transition-colors"
                                title={c.snippet || ''}
                              >
                                [{c.number}] {c.document_name}
                              </span>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Source cards */}
                      {turn.answer!.sources && turn.answer!.sources.length > 0 && (
                        <div className="mt-6">
                          <div className="text-[11px] font-bold text-outline uppercase tracking-wider mb-3">
                            Nguồn tham khảo ({turn.answer!.sources.length})
                          </div>
                          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                            {turn.answer!.sources.map((src, i) => (
                              <div
                                key={i}
                                className="p-3 bg-white border border-outline-variant rounded-xl shadow-sm hover:shadow-md transition-shadow cursor-pointer flex gap-3 group dark:bg-slate-900 dark:border-slate-700"
                              >
                                <div className="w-10 h-10 rounded-lg bg-white border border-outline-variant/30 flex items-center justify-center shrink-0">
                                  <FileTypeIcon fileName={src.doc_name} size={24} />
                                </div>
                                <div className="flex-1 min-w-0">
                                  <p className="text-[11px] font-bold truncate group-hover:text-primary transition-colors text-on-surface dark:text-white">
                                    {src.doc_name}
                                  </p>
                                  <p className="text-[10px] text-on-surface-variant truncate">
                                    {src.hub_name}
                                  </p>
                                  <p className="text-[10px] text-primary mt-1 font-semibold">
                                    Match {formatScore(src.score)}%
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Feedback */}
                      <div className="flex items-center gap-1.5 mt-4 pt-3 border-t border-outline-variant">
                        <span className="text-[11px] text-outline mr-1">Câu trả lời hữu ích?</span>
                        <button
                          onClick={() => setFeedback(turn.id, 'up')}
                          className={cn(
                            'p-1.5 rounded-lg transition-colors',
                            turn.feedback === 'up'
                              ? 'bg-emerald-100 text-emerald-600 dark:bg-emerald-900/30'
                              : 'text-outline hover:bg-surface-container',
                          )}
                        >
                          <ThumbsUp size={14} />
                        </button>
                        <button
                          onClick={() => setFeedback(turn.id, 'down')}
                          className={cn(
                            'p-1.5 rounded-lg transition-colors',
                            turn.feedback === 'down'
                              ? 'bg-error-container text-on-error-container'
                              : 'text-outline hover:bg-surface-container',
                          )}
                        >
                          <ThumbsDown size={14} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </React.Fragment>
          ))}
        </div>

        {/* Input area — compact: suggestions inline với toolbar dưới textarea */}
        <div className="px-6 py-3 border-t border-outline-variant bg-surface-bright shrink-0">
          <div>
            {/* Textarea container with 2px primary border */}
            <div className="relative group">
              <div className="absolute inset-0 bg-primary/5 rounded-2xl blur-md opacity-0 group-focus-within:opacity-100 transition-opacity" />
              <div className="relative bg-white border-2 border-primary/20 rounded-2xl shadow-sm focus-within:border-primary focus-within:ring-4 focus-within:ring-primary/10 transition-all overflow-hidden p-3 dark:bg-slate-800">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={1}
                  placeholder={turns.length === 0
                    ? "Nhập câu hỏi của bạn..."
                    : "Bạn có câu hỏi khác? Hãy đặt câu hỏi để nhận câu trả lời chính xác từ kho tri thức..."}
                  className="w-full border-none focus:ring-0 text-body-md py-1.5 px-1 resize-none max-h-32 outline-none bg-transparent placeholder:text-on-surface-variant/60 text-on-surface dark:text-white"
                />
                {/* Bottom toolbar: attach + suggestion chips scroll + send — 1 dòng compact */}
                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-outline-variant/50">
                  <div className="flex gap-1 shrink-0">
                    <button
                      className="p-1.5 hover:bg-surface-container rounded-lg text-outline hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title="Đính kèm tệp (sắp ra mắt)"
                      disabled
                    >
                      <Paperclip size={18} />
                    </button>
                    <button
                      className="p-1.5 hover:bg-surface-container rounded-lg text-outline hover:text-primary transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                      title="Đính kèm ảnh (sắp ra mắt)"
                      disabled
                    >
                      <ImageIcon size={18} />
                    </button>
                  </div>
                  {/* Suggestion chips — scroll horizontal, chiếm flex-1 giữa attach và send */}
                  <div className="flex-1 flex gap-1.5 overflow-x-auto no-scrollbar min-w-0">
                    {QUICK_TOPICS.map((topic) => (
                      <button
                        key={topic}
                        onClick={() => setInput(topic + ': ')}
                        className="px-2.5 py-1 bg-surface-container-low border border-outline-variant rounded-full text-[11px] font-semibold hover:border-primary hover:text-primary transition-all whitespace-nowrap text-on-surface-variant shrink-0 dark:bg-slate-900 dark:border-slate-700"
                      >
                        {topic}
                      </button>
                    ))}
                  </div>
                  <button
                    onClick={() => handleAsk()}
                    disabled={isAsking || !input.trim()}
                    className="shrink-0 w-9 h-9 rounded-xl bg-primary text-on-primary flex items-center justify-center shadow-lg hover:shadow-primary/30 hover:scale-105 transition-all active:scale-95 disabled:opacity-50 disabled:grayscale disabled:scale-100"
                  >
                    {isAsking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} className="-rotate-45" />}
                  </button>
                </div>
              </div>
            </div>
            <p className="mt-2 text-center text-[10px] text-outline">
              AI có thể mắc lỗi. Vui lòng kiểm tra thông tin quan trọng.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
};

export default CrossHubSearch;
