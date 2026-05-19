import React, { useState, useEffect, useRef, useMemo } from 'react';
import { api, type HubAPI, type SearchResultAPI, type SearchAnswerAPI } from '../services/api';
import { cn } from '../lib/utils';
import {
  Search,
  Filter,
  Loader2,
  Sparkles,
  Bot,
  Send,
  BookOpen,
  ThumbsUp,
  ThumbsDown,
  ChevronDown,
  ChevronUp,
  User as UserIcon,
  AlertTriangle,
  Check,
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

const formatDocDate = (s?: string) => {
  if (!s) return '';
  const d = new Date(s);
  if (Number.isNaN(d.getTime())) return '';
  return `${d.toLocaleDateString('vi-VN')} ${d.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
  })}`;
};

/** Avatar mascot cho câu trả lời AI — fallback về icon Sparkles nếu thiếu ảnh. */
const AssistantAvatar = () => {
  const [imgOk, setImgOk] = useState(true);
  return (
    <div className="shrink-0 w-9 h-9 rounded-xl bg-slate-100 dark:bg-slate-700 overflow-hidden flex items-center justify-center">
      {imgOk ? (
        <img
          src="/mascot.png"
          alt="Trợ lý Medinet Wiki"
          className="w-full h-full object-contain"
          onError={() => setImgOk(false)}
        />
      ) : (
        <Sparkles size={16} className="text-brand-indigo" />
      )}
    </div>
  );
};

const CrossHubSearch = () => {
  const { user } = useAuth();
  const userName = user?.user.name || 'bạn';

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
  const hasConversation = turns.length > 0;

  return (
    <div className="h-full flex gap-5">
      {/* ─── Cột trái: Tri thức đã trích xuất ─── */}
      <aside className="hidden lg:flex w-[340px] shrink-0 flex-col glass-card overflow-hidden">
        <div className="px-4 py-3.5 border-b border-slate-200/60 dark:border-slate-700/60 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-900 dark:text-white">Tri thức đã trích xuất</h2>
          <div className="relative">
            <button
              onClick={() => setHubMenuOpen((v) => !v)}
              className={cn(
                'p-1.5 rounded-lg transition-colors',
                selectedHubId
                  ? 'bg-accent/10 text-accent'
                  : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700 dark:hover:text-slate-200',
              )}
              title="Lọc theo Hub"
            >
              <Filter size={15} />
            </button>
            <AnimatePresence>
              {hubMenuOpen && (
                <>
                  <div className="fixed inset-0 z-40" onClick={() => setHubMenuOpen(false)} />
                  <motion.div
                    initial={{ opacity: 0, scale: 0.95, y: -6 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.95, y: -6 }}
                    className="absolute right-0 mt-2 w-56 glass-card z-50 overflow-hidden p-1.5"
                  >
                    <p className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
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
                          'w-full flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg text-xs transition-colors',
                          selectedHubId === h.id
                            ? 'bg-accent/10 text-accent font-semibold'
                            : 'text-slate-600 dark:text-slate-300 hover:bg-slate-100 dark:hover:bg-slate-700',
                        )}
                      >
                        <span className="truncate">{h.name}</span>
                        {selectedHubId === h.id && <Check size={13} className="shrink-0" />}
                      </button>
                    ))}
                  </motion.div>
                </>
              )}
            </AnimatePresence>
          </div>
        </div>

        {/* Ô tìm kiếm tri thức */}
        <div className="p-3 border-b border-slate-200/60 dark:border-slate-700/60">
          <div className="relative">
            <Search size={15} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={kbFilter}
              onChange={(e) => setKbFilter(e.target.value)}
              placeholder="Tìm kiếm tri thức..."
              className="input-field w-full pl-9 text-xs py-2"
            />
          </div>
        </div>

        {/* Danh sách thẻ tri thức */}
        <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
          {knowledge.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center px-4 text-slate-400 dark:text-slate-500">
              <BookOpen size={36} className="opacity-20 mb-3" />
              <p className="text-xs font-medium">Chưa có tri thức</p>
              <p className="text-[11px] mt-1">Đặt câu hỏi để hệ thống trích xuất tri thức liên quan.</p>
            </div>
          ) : filteredKnowledge.length === 0 ? (
            <p className="text-xs text-slate-400 text-center py-8">
              Không có tri thức khớp "{kbFilter}".
            </p>
          ) : (
            <>
              {visibleKnowledge.map((k) => (
                <button
                  key={k.id}
                  onClick={() => setExpandedKbId(expandedKbId === k.id ? null : k.id)}
                  className="w-full text-left rounded-xl border border-slate-200/70 dark:border-slate-700/70 p-3 hover:border-accent/40 hover:shadow-sm transition-all group"
                >
                  <span className="inline-block text-[10px] font-semibold text-white bg-brand-indigo px-2 py-0.5 rounded-md mb-2">
                    {k.hub_name}
                  </span>
                  <h3 className="text-xs font-bold text-slate-900 dark:text-white leading-snug mb-1 line-clamp-1">
                    {k.title}
                  </h3>
                  <p
                    className={cn(
                      'text-[11px] text-slate-500 dark:text-slate-400 leading-relaxed',
                      expandedKbId === k.id ? 'whitespace-pre-line' : 'line-clamp-3',
                    )}
                  >
                    {(k.content || k.snippet).replace(/^#{1,4}\s+/gm, '').replace(/\*\*/g, '')}
                  </p>
                  <div className="flex items-center justify-between mt-2.5">
                    <span className="text-xs font-bold text-brand-indigo tabular-nums">
                      {formatScore(k.score)}%
                    </span>
                    <span className="text-[10px] text-slate-400 dark:text-slate-500">
                      {formatDocDate(k.updated_at)}
                    </span>
                  </div>
                </button>
              ))}

              {filteredKnowledge.length > KB_PREVIEW && (
                <button
                  onClick={() => setKbExpanded((v) => !v)}
                  className="w-full flex items-center justify-center gap-1 py-2 text-xs font-medium text-slate-500 dark:text-slate-400 hover:text-accent rounded-lg hover:bg-slate-100 dark:hover:bg-slate-700/50 transition-colors"
                >
                  {kbExpanded ? (
                    <>
                      Thu gọn <ChevronUp size={13} />
                    </>
                  ) : (
                    <>
                      Xem thêm ({filteredKnowledge.length - KB_PREVIEW}) <ChevronDown size={13} />
                    </>
                  )}
                </button>
              )}
            </>
          )}
        </div>
      </aside>

      {/* ─── Cột phải: Hỏi - đáp AI ─── */}
      <section className="flex-1 flex flex-col min-w-0">
        <div ref={scrollRef} className="flex-1 overflow-y-auto pr-1 space-y-5">
          {/* Thẻ chào mừng + ô nhập câu hỏi — ẩn sau khi đã có hội thoại */}
          {!hasConversation && (
            <div className="glass-card p-5 sm:p-7 relative overflow-hidden">
              <div className="absolute -right-8 -top-8 w-40 h-40 rounded-full bg-gradient-to-br from-brand-indigo/10 to-brand-purple/10 hidden sm:block" />
              <div className="absolute right-7 top-7 hidden sm:flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-brand-indigo to-brand-purple text-white shadow-primary">
                <Bot size={30} />
              </div>
              <h1 className="text-h1 font-bold text-slate-900 dark:text-white tracking-tight">
                Xin chào {userName}! <span className="inline-block">👋</span>
              </h1>
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400 mt-1.5 mb-5 max-w-xl">
                Tôi là trợ lý tri thức Medinet Wiki. Bạn có thể đặt câu hỏi về quy trình, hướng dẫn,
                văn bản, biểu mẫu...
              </p>

              <div className="flex items-center gap-2.5 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 shadow-sm focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10 transition-all">
                <textarea
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                  rows={2}
                  placeholder="Nhập câu hỏi của bạn..."
                  className="flex-1 bg-transparent text-sm outline-none resize-none py-0.5 max-h-40 placeholder:text-slate-400 dark:placeholder:text-slate-500 dark:text-white"
                />
                <button
                  onClick={() => handleAsk()}
                  disabled={isAsking || !input.trim()}
                  className="shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-brand-indigo text-white hover:bg-brand-indigo/90 disabled:opacity-40 transition-colors"
                >
                  {isAsking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              </div>
              <p className="text-[10px] text-slate-400 dark:text-slate-500 mt-2.5">
                Nhấn Enter để gửi · Shift + Enter để xuống dòng
              </p>
            </div>
          )}

          {/* Hội thoại */}
          {turns.map((turn) => (
            <div key={turn.id} className="space-y-4">
              {/* Câu hỏi của người dùng */}
              <div className="flex items-start justify-end gap-2.5">
                <div className="flex flex-col items-end max-w-[78%]">
                  <div className="bg-brand-indigo text-white text-sm rounded-2xl rounded-tr-md px-4 py-2.5 whitespace-pre-line">
                    {turn.question}
                  </div>
                  <span className="text-[10px] text-slate-400 mt-1 mr-1">
                    {formatClock(turn.askedAt)}
                  </span>
                </div>
                <div className="shrink-0 w-8 h-8 rounded-full bg-slate-200 dark:bg-slate-700 flex items-center justify-center text-slate-500 dark:text-slate-300">
                  <UserIcon size={15} />
                </div>
              </div>

              {/* Câu trả lời AI */}
              <div className="flex items-start gap-2.5">
                <AssistantAvatar />
                <div className="flex-1 min-w-0">
                  {!turn.answer && !turn.error ? (
                    <div className="glass-card px-4 py-3.5 inline-flex items-center gap-2 text-sm text-slate-400">
                      <Loader2 size={14} className="animate-spin" />
                      Đang soạn câu trả lời...
                    </div>
                  ) : turn.error ? (
                    <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800 rounded-2xl rounded-tl-md p-3.5 flex items-start gap-2.5">
                      <AlertTriangle size={15} className="text-amber-500 shrink-0 mt-0.5" />
                      <p className="text-xs text-amber-700 dark:text-amber-300 font-medium leading-relaxed">
                        {turn.error}
                      </p>
                    </div>
                  ) : (
                    <div className="glass-card p-4 sm:p-5 rounded-tl-md">
                      <div className="flex items-center gap-2 mb-2.5">
                        <span className="text-[10px] px-2 py-0.5 bg-accent/10 text-accent rounded-full font-semibold">
                          {turn.answer!.model}
                        </span>
                        <span className="text-[10px] text-slate-400 ml-auto">
                          {turn.answeredAt ? formatClock(turn.answeredAt) : ''} ·{' '}
                          {(turn.answer!.query_time_ms / 1000).toFixed(1)}s
                        </span>
                      </div>

                      <CitationText text={turn.answer!.answer} citations={turn.answer!.citations} />

                      {/* Nguồn tham khảo */}
                      {turn.answer!.sources && turn.answer!.sources.length > 0 && (
                        <div className="mt-4 pt-3.5 border-t border-slate-100 dark:border-slate-700">
                          <p className="text-xs font-semibold text-slate-500 dark:text-slate-400 mb-2.5">
                            Nguồn tham khảo ({turn.answer!.sources.length})
                          </p>
                          <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-3 gap-2">
                            {turn.answer!.sources.map((src, i) => (
                              <div
                                key={i}
                                className="flex items-start gap-2.5 p-2.5 rounded-xl border border-slate-200/70 dark:border-slate-700/70 bg-slate-50/60 dark:bg-slate-800/40"
                              >
                                <FileTypeIcon
                                  fileName={src.doc_name}
                                  size={32}
                                  className="shrink-0"
                                />
                                <div className="min-w-0">
                                  <p className="text-[11px] font-semibold text-slate-700 dark:text-slate-200 truncate">
                                    {src.doc_name}
                                  </p>
                                  <p className="text-[10px] text-slate-400 truncate">
                                    {src.hub_name}
                                  </p>
                                  <p className="text-[10px] text-slate-400">
                                    Match {formatScore(src.score)}%
                                  </p>
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* Phản hồi hữu ích */}
                      <div className="flex items-center gap-1.5 mt-3.5 pt-3 border-t border-slate-100 dark:border-slate-700">
                        <span className="text-[11px] text-slate-400 mr-1">Câu trả lời hữu ích?</span>
                        <button
                          onClick={() => setFeedback(turn.id, 'up')}
                          className={cn(
                            'p-1.5 rounded-lg transition-colors',
                            turn.feedback === 'up'
                              ? 'bg-success/10 text-success'
                              : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700',
                          )}
                        >
                          <ThumbsUp size={13} />
                        </button>
                        <button
                          onClick={() => setFeedback(turn.id, 'down')}
                          className={cn(
                            'p-1.5 rounded-lg transition-colors',
                            turn.feedback === 'down'
                              ? 'bg-danger/10 text-danger'
                              : 'text-slate-400 hover:bg-slate-100 hover:text-slate-600 dark:hover:bg-slate-700',
                          )}
                        >
                          <ThumbsDown size={13} />
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Ô nhập câu hỏi tiếp theo (dính đáy) */}
        {hasConversation && (
          <div className="shrink-0 pt-4">
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-700 rounded-2xl px-4 py-3 shadow-sm focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10 transition-all">
              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                rows={1}
                placeholder="Bạn có câu hỏi khác? Hãy đặt câu hỏi để nhận câu trả lời chính xác từ kho tri thức..."
                className="w-full bg-transparent text-sm outline-none resize-none py-1 max-h-32 placeholder:text-slate-400 dark:placeholder:text-slate-500 dark:text-white"
              />
              <div className="flex items-end justify-between gap-2 mt-2">
                <div className="flex flex-wrap gap-1.5">
                  {QUICK_TOPICS.map((topic) => (
                    <button
                      key={topic}
                      onClick={() => setInput(topic + ': ')}
                      className="px-2.5 py-1 text-[11px] font-medium text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 rounded-full transition-colors"
                    >
                      {topic}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => handleAsk()}
                  disabled={isAsking || !input.trim()}
                  className="shrink-0 w-10 h-10 flex items-center justify-center rounded-xl bg-brand-indigo text-white hover:bg-brand-indigo/90 disabled:opacity-40 transition-colors"
                >
                  {isAsking ? <Loader2 size={16} className="animate-spin" /> : <Send size={16} />}
                </button>
              </div>
            </div>
            <p className="text-[10px] text-slate-400 dark:text-slate-500 text-center mt-2">
              AI có thể mắc lỗi. Vui lòng kiểm tra thông tin quan trọng.
            </p>
          </div>
        )}
      </section>
    </div>
  );
};

export default CrossHubSearch;
