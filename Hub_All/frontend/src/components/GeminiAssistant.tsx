import { useState, useRef, useEffect } from 'react';
import { Sparkles, X, Send, Bot, User, Loader2, Minimize2, Maximize2 } from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import ReactMarkdown from 'react-markdown';
import rehypeSanitize from 'rehype-sanitize';
import { cn } from '../lib/utils';
import { api } from '../services/api';

interface Message {
  role: 'user' | 'model';
  content: string;
}

export default function GeminiAssistant() {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [input, setInput] = useState('');
  const [messages, setMessages] = useState<Message[]>([
    { role: 'model', content: 'Xin chào! Tôi là AI Assistant. Tôi có thể giúp gì cho bạn trong việc quản lý Medinet Wiki Hub?' }
  ]);
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsLoading(true);

    try {
      const res = await api.aiChat(
        [...messages, { role: 'user', content: userMessage }],
        "Bạn là một trợ lý AI thông minh tích hợp trong hệ thống Medinet Wiki Hub. Hệ thống này quản lý các Hub y tế, người dùng, tài liệu RAG và hàng đợi đồng bộ. Hãy trả lời ngắn gọn, chuyên nghiệp và hữu ích bằng tiếng Việt. Nếu người dùng hỏi về cách sử dụng, hãy hướng dẫn họ dựa trên các tính năng như Hub Registry, User Management, Sync Queue, và Document Ingestion.",
      );
      const aiResponse = res.success && res.data?.response
        ? res.data.response
        : "Xin lỗi, tôi không thể trả lời lúc này.";
      setMessages(prev => [...prev, { role: 'model', content: aiResponse }]);
    } catch (error) {
      console.error("AI Error:", error);
      setMessages(prev => [...prev, { role: 'model', content: "Đã có lỗi xảy ra khi kết nối với AI. Vui lòng thử lại sau." }]);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-[100]">
      <AnimatePresence>
        {!isOpen && (
          <motion.button
            initial={{ scale: 0, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0, opacity: 0 }}
            onClick={() => setIsOpen(true)}
            className="w-14 h-14 rounded-full bg-brand-indigo text-white shadow-lg flex items-center justify-center transition-colors hover:bg-brand-indigo/90"
          >
            <Sparkles />
          </motion.button>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.95 }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
              height: isMinimized ? '64px' : '500px',
            }}
            exit={{ opacity: 0, y: 20, scale: 0.95 }}
            className={cn(
              "glass-card shadow-lg flex flex-col overflow-hidden border-brand-indigo/20",
              isMinimized ? "w-[200px]" : "w-[calc(100vw-3rem)] sm:w-[380px]"
            )}
          >
            {/* Header */}
            <div className="p-4 bg-brand-indigo text-white flex items-center justify-between shrink-0">
              <div className="flex items-center gap-2">
                <Sparkles size={18} />
                <span className="font-bold text-sm">AI Assistant</span>
              </div>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => setIsMinimized(!isMinimized)}
                  className="p-1 hover:bg-white/20 rounded transition-colors"
                >
                  {isMinimized ? <Maximize2 size={16} /> : <Minimize2 size={16} />}
                </button>
                <button
                  onClick={() => setIsOpen(false)}
                  className="p-1 hover:bg-white/20 rounded transition-colors"
                >
                  <X size={16} />
                </button>
              </div>
            </div>

            {!isMinimized && (
              <>
                {/* Messages */}
                <div className="flex-1 overflow-y-auto p-4 space-y-4 bg-slate-50/50 dark:bg-slate-800/50">
                  {messages.map((m, i) => (
                    <div key={i} className={cn("flex gap-3", m.role === 'user' ? "flex-row-reverse" : "")}>
                      <div className={cn(
                        "w-8 h-8 rounded-full flex items-center justify-center shrink-0 shadow-sm",
                        m.role === 'user' ? "bg-accent text-white" : "bg-white dark:bg-slate-800 text-brand-indigo border border-brand-indigo/10"
                      )}>
                        {m.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                      </div>
                      <div className={cn(
                        "max-w-[80%] p-3 rounded-2xl text-sm shadow-sm",
                        m.role === 'user'
                          ? "bg-accent text-white rounded-tr-none"
                          : "bg-white dark:bg-slate-800 text-slate-800 dark:text-slate-100 border border-slate-100 dark:border-slate-700 rounded-tl-none"
                      )}>
                        <div className="prose prose-sm prose-slate max-w-none dark:prose-invert">
                          <ReactMarkdown rehypePlugins={[rehypeSanitize]}>{m.content}</ReactMarkdown>
                        </div>
                      </div>
                    </div>
                  ))}
                  {isLoading && (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-white dark:bg-slate-800 text-brand-indigo border border-brand-indigo/10 flex items-center justify-center shrink-0 shadow-sm">
                        <Bot size={16} />
                      </div>
                      <div className="bg-white dark:bg-slate-800 border border-slate-100 dark:border-slate-700 p-3 rounded-2xl rounded-tl-none shadow-sm">
                        <Loader2 size={16} className="animate-spin text-brand-indigo" />
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="p-4 bg-white dark:bg-slate-800 border-t border-slate-100 dark:border-slate-700 flex gap-2">
                  <input
                    type="text"
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={(e) => e.key === 'Enter' && handleSend()}
                    placeholder="Hỏi AI..."
                    className="flex-1 bg-slate-100 dark:bg-slate-700 border-none rounded-full px-4 py-2 text-sm focus:ring-2 focus:ring-brand-indigo/20 outline-none transition-all"
                  />
                  <button
                    onClick={handleSend}
                    disabled={!input.trim() || isLoading}
                    className="w-10 h-10 rounded-full bg-brand-indigo text-white flex items-center justify-center hover:bg-brand-indigo/90 transition-colors disabled:opacity-50"
                  >
                    <Send size={18} />
                  </button>
                </div>
              </>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
