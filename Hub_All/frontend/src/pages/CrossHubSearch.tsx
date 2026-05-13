import React, { useState, useEffect } from 'react';
import { api, type HubAPI, type SearchResultAPI, type SearchAnswerAPI } from '../services/api';
import { cn } from '../lib/utils';
import { Search, Filter, ExternalLink, Clock, Tag, AlertTriangle, Loader2, Sparkles, BookOpen, ChevronDown, ChevronUp } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import CitationText from '../components/CitationText';

const CrossHubSearch = () => {
  const [query, setQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const [results, setResults] = useState<SearchResultAPI[]>([]);
  const [hasSearched, setHasSearched] = useState(false);
  const [hubs, setHubs] = useState<HubAPI[]>([]);
  const [selectedHubId, setSelectedHubId] = useState('');
  const [queryTimeMs, setQueryTimeMs] = useState(0);
  const [totalHubsSearched, setTotalHubsSearched] = useState(0);
  const [error, setError] = useState('');
  const [aiAnswer, setAiAnswer] = useState<SearchAnswerAPI | null>(null);
  const [showSources, setShowSources] = useState(false);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  useEffect(() => {
    api.getHubs().then(res => {
      if (res.success && res.data) {
        setHubs(res.data.filter(h => h.status === 'active'));
      }
    });
  }, []);

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsSearching(true);
    setHasSearched(true);
    setError('');
    setAiAnswer(null);
    setShowSources(false);

    try {
      const hubIds = selectedHubId ? [selectedHubId] : [];

      // Call RAG answer API (returns AI answer + search results)
      const answerRes = await api.searchAnswer({
        query: query.trim(),
        hub_ids: hubIds,
        top_k: 5,
      });

      if (answerRes.success && answerRes.data) {
        setAiAnswer(answerRes.data);
        setResults(answerRes.data.search_results || []);
        setQueryTimeMs(answerRes.data.query_time_ms);
        setTotalHubsSearched(answerRes.data.sources?.length || 0);
      } else {
        // AI answer failed — fallback to regular search (no error shown)
        const res = await api.crossHubSearch({ query: query.trim(), hub_ids: hubIds, top_k: 20 });
        if (res.success && res.data) {
          setResults(res.data.results || []);
          setQueryTimeMs(res.data.query_time_ms);
          setTotalHubsSearched(res.data.total_hubs_searched);
        }
        // Don't show error — search results are enough
      }
    } catch {
      setError('Không thể kết nối tới server');
      setResults([]);
    } finally {
      setIsSearching(false);
    }
  };

  const formatScore = (score: number) => Math.round(score * 100);

  const formatTime = (dateStr?: string) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / 86400000);
    if (diffDays === 0) return 'Hôm nay';
    if (diffDays === 1) return '1 ngày trước';
    if (diffDays < 7) return `${diffDays} ngày trước`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} tuần trước`;
    return d.toLocaleDateString('vi-VN');
  };

  return (
    <div className="h-full flex flex-col space-y-6">
      <div className={cn(
        "transition-all duration-500 flex flex-col items-center",
        hasSearched ? "mt-0" : "mt-[15vh]"
      )}>
        <h1 className={cn(
          "font-bold text-slate-900 dark:text-white tracking-tight transition-all text-center sm:text-left",
          hasSearched ? "text-lg sm:text-xl mb-4 self-start" : "text-3xl sm:text-4xl mb-8"
        )}>
          Tìm kiếm Cross-Hub
        </h1>

        <form onSubmit={handleSearch} className={cn(
          "w-full transition-all",
          hasSearched ? "max-w-none" : "max-w-2xl"
        )}>
          <div className={cn(
            "flex items-center gap-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 shadow-sm px-4 sm:px-2 sm:ps-5 transition-all focus-within:border-accent focus-within:ring-4 focus-within:ring-accent/10",
            hasSearched ? "rounded-xl sm:rounded-2xl" : "rounded-full"
          )}>
            <Search className="text-slate-400 dark:text-slate-500 shrink-0" size={hasSearched ? 18 : 20} />
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Tìm kiếm trên Wiki Medinet..."
              className={cn(
                "flex-1 bg-transparent py-3 sm:py-3.5 text-sm sm:text-base outline-none placeholder:text-slate-400 dark:placeholder:text-slate-500 dark:text-white"
              )}
            />
            <button
              type="submit"
              disabled={isSearching}
              className="shrink-0 bg-brand-indigo text-white text-md font-medium px-5 py-2 rounded-full transition-colors hover:bg-brand-indigo/90 disabled:opacity-60"
            >
              {isSearching ? <Loader2 size={16} className="animate-spin" /> : 'Tìm kiếm'}
            </button>
          </div>
          {!hasSearched && (
            <div className="mt-6 flex flex-col items-center space-y-4">
              <p className="text-slate-500 dark:text-slate-400 text-[10px] sm:text-sm font-medium text-center px-4">Tìm kiếm ngữ nghĩa (RAG) — kết quả từ tất cả Hub</p>
              <div className="flex flex-wrap justify-center gap-2 px-4">
                {['Quy trình vận hành', 'Bài thuốc đông y', 'Chính sách nhân sự'].map(chip => (
                  <button
                    key={chip}
                    onClick={() => { setQuery(chip); }}
                    className="px-3 sm:px-4 py-1 sm:py-1.5 bg-slate-100 dark:bg-slate-700 hover:bg-slate-200 dark:hover:bg-slate-600 text-slate-600 dark:text-slate-300 rounded-full text-[10px] sm:text-xs font-medium transition-colors"
                  >
                    {chip}
                  </button>
                ))}
              </div>
            </div>
          )}
        </form>
      </div>

      <AnimatePresence>
        {hasSearched && (
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex-1 flex flex-col space-y-6"
          >
            <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2">
              <p className="text-xs sm:text-sm text-slate-500 dark:text-slate-400">
                {isSearching ? 'Đang tìm kiếm...' : `Tìm thấy ${results.length} kết quả từ ${totalHubsSearched} Hub (${(queryTimeMs / 1000).toFixed(1)}s)`}
              </p>
              <div className="flex items-center gap-2">
                <Filter size={14} className="text-slate-400 dark:text-slate-500" />
                <select
                  className="bg-transparent text-xs text-slate-600 dark:text-slate-300 outline-none cursor-pointer"
                  value={selectedHubId}
                  onChange={(e) => setSelectedHubId(e.target.value)}
                >
                  <option value="">Tất cả Hub</option>
                  {hubs.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                </select>
              </div>
            </div>

            {error && (
              <div className="bg-amber-50 dark:bg-amber-900/20 border border-amber-100 dark:border-amber-800 rounded-xl p-3 flex items-center gap-3">
                <AlertTriangle size={16} className="text-amber-500 shrink-0" />
                <p className="text-xs text-amber-700 dark:text-amber-300 font-medium">{error}</p>
              </div>
            )}

            {/* AI Answer Card */}
            {aiAnswer && (
              <motion.div
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                className="glass-card border border-accent/20 overflow-hidden"
              >
                <div className="p-5 bg-gradient-to-r from-accent/5 to-brand-indigo/5 dark:from-accent/10 dark:to-brand-indigo/10 border-b border-accent/10">
                  <div className="flex items-center gap-2 mb-3">
                    <Sparkles size={16} className="text-accent" />
                    <span className="text-sm font-semibold text-slate-800 dark:text-slate-100">Trả lời từ AI</span>
                    <span className="text-[10px] px-2 py-0.5 bg-accent/10 text-accent rounded-full font-medium">{aiAnswer.model}</span>
                    <span className="text-[10px] text-slate-400 ml-auto">{(aiAnswer.query_time_ms / 1000).toFixed(1)}s</span>
                  </div>
                  <CitationText
                    text={aiAnswer.answer}
                    citations={aiAnswer.citations}
                  />
                </div>
                {aiAnswer.sources && aiAnswer.sources.length > 0 && (
                  <div className="px-5 py-3 bg-slate-50/50 dark:bg-slate-800/50">
                    <button
                      onClick={() => setShowSources(!showSources)}
                      className="flex items-center gap-1.5 text-xs text-slate-500 dark:text-slate-400 hover:text-accent transition-colors"
                    >
                      <BookOpen size={12} />
                      <span className="font-medium">{aiAnswer.sources.length} nguồn tham khảo</span>
                      {showSources ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
                    </button>
                    {showSources && (
                      <motion.div
                        initial={{ opacity: 0, height: 0 }}
                        animate={{ opacity: 1, height: 'auto' }}
                        className="mt-3 space-y-2"
                      >
                        {aiAnswer.sources.map((src, i) => (
                          <div key={i} className="flex items-start gap-2 p-2 bg-white dark:bg-slate-800 rounded-lg border border-slate-100 dark:border-slate-700">
                            <span className="text-[10px] font-bold text-accent bg-accent/10 px-1.5 py-0.5 rounded shrink-0">{i + 1}</span>
                            <div className="min-w-0">
                              <p className="text-xs font-medium text-slate-700 dark:text-slate-200 truncate">{src.doc_name}</p>
                              <p className="text-[10px] text-slate-400">{src.hub_name} · Match {Math.round(src.score * 100)}%</p>
                            </div>
                          </div>
                        ))}
                      </motion.div>
                    )}
                  </div>
                )}
              </motion.div>
            )}

            <div className="space-y-4 pb-12">
              {isSearching ? (
                Array.from({ length: 3 }).map((_, i) => (
                  <div key={i} className="glass-card p-6 space-y-3 animate-pulse">
                    <div className="h-3 w-32 bg-slate-100 dark:bg-slate-700 rounded" />
                    <div className="h-5 w-64 bg-slate-100 dark:bg-slate-700 rounded" />
                    <div className="space-y-2">
                      <div className="h-3 w-full bg-slate-100 dark:bg-slate-700 rounded" />
                      <div className="h-3 w-3/4 bg-slate-100 dark:bg-slate-700 rounded" />
                    </div>
                  </div>
                ))
              ) : results.length > 0 ? (
                results.map((res, idx) => (
                  <motion.div
                    key={res.id}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: idx * 0.05 }}
                    className="glass-card overflow-hidden hover:shadow-md transition-all"
                  >
                    {/* Score bar */}
                    <div className="h-1 bg-slate-100 dark:bg-slate-700">
                      <div className="h-full bg-gradient-to-r from-accent to-brand-indigo" style={{ width: `${formatScore(res.score)}%` }} />
                    </div>

                    <div
                      className="p-5 cursor-pointer"
                      onClick={() => setExpandedId(expandedId === res.id ? null : res.id)}
                    >
                      {/* Header */}
                      <div className="flex justify-between items-start mb-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-[10px] font-bold text-white bg-accent px-2 py-0.5 rounded-full">{res.hub_name}</span>
                          {res.category && (
                            <span className="text-[10px] font-medium text-slate-500 dark:text-slate-400 bg-slate-100 dark:bg-slate-700 px-2 py-0.5 rounded-full flex items-center gap-1">
                              <BookOpen size={9} /> {res.category}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <div className={cn(
                            "w-2 h-2 rounded-full",
                            formatScore(res.score) >= 70 ? "bg-success" : formatScore(res.score) >= 50 ? "bg-amber-400" : "bg-slate-300"
                          )} />
                          <span className="text-sm font-bold text-slate-700 dark:text-slate-200 tabular-nums">{formatScore(res.score)}%</span>
                          {expandedId === res.id ? <ChevronUp size={14} className="text-slate-400" /> : <ChevronDown size={14} className="text-slate-400" />}
                        </div>
                      </div>

                      {/* Title */}
                      <h3 className="text-base font-bold text-slate-900 dark:text-white mb-2">{res.title}</h3>

                      {/* Snippet (collapsed view) */}
                      {expandedId !== res.id && (
                        <p className="text-sm text-slate-600 dark:text-slate-300 leading-relaxed line-clamp-2">{res.snippet}</p>
                      )}
                    </div>

                    {/* Expanded detail view */}
                    <AnimatePresence>
                      {expandedId === res.id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          exit={{ opacity: 0, height: 0 }}
                          className="border-t border-slate-100 dark:border-slate-700"
                        >
                          <div className="p-5 space-y-4">
                            {/* Full content */}
                            <div className="p-4 bg-slate-50 dark:bg-slate-800/50 rounded-xl border border-slate-100 dark:border-slate-700">
                              <p className="text-sm text-slate-700 dark:text-slate-200 leading-relaxed whitespace-pre-line">
                                {(res.content || res.snippet).replace(/^#{1,4}\s+/gm, '').replace(/\*\*/g, '')}
                              </p>
                            </div>

                            {/* Metadata */}
                            <div className="flex items-center gap-4 flex-wrap text-[11px] text-slate-400 dark:text-slate-500">
                              <span className="flex items-center gap-1"><BookOpen size={11} /> Nguồn: {res.category || res.title}</span>
                              <span className="flex items-center gap-1">Similarity: {(res.raw_similarity * 100).toFixed(1)}%</span>
                              <span className="flex items-center gap-1">Score: {formatScore(res.score)}%</span>
                              {res.updated_at && <span className="flex items-center gap-1"><Clock size={11} /> {formatTime(res.updated_at)}</span>}
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>

                    {/* Footer tags (always visible) */}
                    {res.tags && res.tags.length > 0 && (
                      <div className="px-5 pb-4 flex items-center gap-2 flex-wrap">
                        {res.tags.map((tag) => (
                          <span key={tag} className="flex items-center gap-1 text-[10px] font-bold text-accent bg-accent/10 px-2 py-0.5 rounded-full">
                            <Tag size={9} /> {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </motion.div>
                ))
              ) : (
                <div className="py-8 sm:py-20 text-center text-slate-400 dark:text-slate-500 space-y-2">
                  <Search size={48} className="mx-auto opacity-10" />
                  <p className="text-sm font-medium">Không tìm thấy nội dung phù hợp trên toàn hệ thống</p>
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default CrossHubSearch;
