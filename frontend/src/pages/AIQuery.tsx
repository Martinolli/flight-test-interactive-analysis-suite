import { useState, useRef, useEffect } from 'react';
import Sidebar from '../components/Sidebar';
import { Card, CardContent } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { ApiService, QueryResponse } from '../services/api';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  Sparkles,
  Send,
  Loader2,
  BookOpen,
  AlertCircle,
  ChevronDown,
  ChevronUp,
  ExternalLink,
} from 'lucide-react';

interface HistoryEntry {
  id: number;
  question: string;
  response: QueryResponse;
  timestamp: Date;
}

const EXAMPLE_QUESTIONS = [
  'What are the minimum control speed requirements per FAR Part 25?',
  'What stall speed margin is required for approach configuration?',
  'What are the MIL-STD-1797 Level 1 flying qualities requirements for pitch?',
  'Describe the test procedure for measuring Vmca in a multi-engine aircraft.',
  'What are the DO-160 environmental test categories for avionics?',
];

function SourceCard({ source }: { source: QueryResponse['sources'][0] }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      <button
        className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-50 transition-colors"
        onClick={() => setOpen((v) => !v)}
      >
        <div className="flex items-center gap-2 min-w-0">
          <BookOpen className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
          <span className="text-xs font-medium text-gray-700 truncate">
            {source.source_id ? `${source.source_id} · ` : ''}
            {source.title || source.filename}
          </span>
          {source.page_numbers && (
            <span className="text-xs text-gray-400 flex-shrink-0">p. {source.page_numbers}</span>
          )}
        </div>
        <div className="flex items-center gap-2 flex-shrink-0 ml-2">
          <span className="text-xs text-gray-400">
            {(source.similarity * 100).toFixed(0)}% match
          </span>
          {open ? <ChevronUp className="w-3 h-3 text-gray-400" /> : <ChevronDown className="w-3 h-3 text-gray-400" />}
        </div>
      </button>
      {open && source.section_title && (
        <div className="px-3 py-2 bg-gray-50 border-t border-gray-100">
          <p className="text-xs text-gray-600 italic">{source.section_title}</p>
        </div>
      )}
    </div>
  );
}

function AnswerCard({ entry }: { entry: HistoryEntry }) {
  const [showSources, setShowSources] = useState(false);

  return (
    <div className="space-y-3">
      {/* Question bubble */}
      <div className="flex justify-end">
        <div className="bg-blue-600 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 max-w-[80%] text-sm">
          {entry.question}
        </div>
      </div>

      {/* Answer bubble */}
      <div className="flex justify-start">
        <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 max-w-[90%] shadow-sm">
          <div className="flex items-center gap-1.5 mb-2">
            <Sparkles className="w-3.5 h-3.5 text-purple-500" />
            <span className="text-xs font-medium text-purple-600">AI Answer</span>
            <span className="text-xs text-gray-400 ml-auto">
              {entry.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>
          <div
            className="
              prose prose-sm max-w-none
              prose-headings:font-semibold prose-headings:text-gray-800
              prose-p:text-gray-800 prose-p:leading-relaxed
              prose-strong:text-gray-900
              prose-ul:my-2 prose-ol:my-2
              prose-table:text-xs prose-table:w-full
              prose-th:bg-gray-50 prose-th:px-2 prose-th:py-1 prose-th:border prose-th:border-gray-200
              prose-td:px-2 prose-td:py-1 prose-td:border prose-td:border-gray-200
              prose-code:bg-gray-100 prose-code:px-1 prose-code:rounded prose-code:text-xs
              prose-pre:bg-gray-900 prose-pre:text-gray-100 prose-pre:rounded-lg prose-pre:p-3
            "
          >
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {entry.response.answer}
            </ReactMarkdown>
          </div>

          {entry.response.sources.length > 0 && (
            <div className="mt-3 pt-3 border-t border-gray-100">
              <button
                onClick={() => setShowSources((v) => !v)}
                className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-700 transition-colors"
              >
                <BookOpen className="w-3.5 h-3.5" />
                {entry.response.sources.length} source{entry.response.sources.length > 1 ? 's' : ''}
                {showSources ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
              </button>
              {showSources && (
                <div className="mt-2 space-y-1.5">
                  {entry.response.sources.map((src, i) => (
                    <SourceCard key={i} source={src} />
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

export default function AIQuery() {
  const [question, setQuestion] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const bottomRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [history, loading]);

  async function handleSubmit() {
    const q = question.trim();
    if (!q || loading) return;
    setQuestion('');
    setLoading(true);
    setError('');
    try {
      const response = await ApiService.queryDocuments(q, 8);
      setHistory((prev) => [
        ...prev,
        { id: Date.now(), question: q, response, timestamp: new Date() },
      ]);
    } catch (err) {
      setError((err as Error).message || 'Query failed');
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }

  function useExample(q: string) {
    setQuestion(q);
    textareaRef.current?.focus();
  }

  return (
    <Sidebar>
      <div className="flex flex-col h-screen max-h-screen p-8 max-w-4xl">
        {/* Header */}
        <div className="mb-6 flex-shrink-0">
          <h1 className="text-3xl font-bold text-gray-900 flex items-center gap-2">
            <Sparkles className="w-7 h-7 text-purple-500" />
            AI Standards Query
          </h1>
          <p className="text-gray-600 mt-1">
            Ask questions about flight test standards and handbooks. Answers are grounded in your
            indexed Document Library.
          </p>
        </div>

        {/* Chat area */}
        <div className="flex-1 overflow-y-auto space-y-6 mb-4 pr-1">
          {history.length === 0 && !loading && (
            <div className="text-center py-12">
              <div className="w-16 h-16 bg-purple-50 rounded-full flex items-center justify-center mx-auto mb-4">
                <Sparkles className="w-8 h-8 text-purple-300" />
              </div>
              <h3 className="text-gray-700 font-medium mb-2">Ask a standards question</h3>
              <p className="text-gray-400 text-sm mb-6 max-w-sm mx-auto">
                Your answers will be sourced from the documents you have indexed in the Document
                Library. Upload MIL-STD, FAR/CS, or DO-xxx PDFs to get started.
              </p>
              <div className="space-y-2 max-w-lg mx-auto text-left">
                <p className="text-xs text-gray-400 font-medium uppercase tracking-wide mb-2">
                  Example questions
                </p>
                {EXAMPLE_QUESTIONS.map((q) => (
                  <button
                    key={q}
                    onClick={() => useExample(q)}
                    className="w-full text-left text-sm text-gray-600 bg-gray-50 hover:bg-gray-100 border border-gray-200 rounded-lg px-3 py-2 transition-colors flex items-center gap-2"
                  >
                    <ExternalLink className="w-3.5 h-3.5 text-gray-400 flex-shrink-0" />
                    {q}
                  </button>
                ))}
              </div>
            </div>
          )}

          {history.map((entry) => (
            <AnswerCard key={entry.id} entry={entry} />
          ))}

          {loading && (
            <div className="flex justify-start">
              <div className="bg-white border border-gray-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm">
                <div className="flex items-center gap-2 text-sm text-gray-500">
                  <Loader2 className="w-4 h-4 animate-spin text-purple-500" />
                  Searching standards and generating answer…
                </div>
              </div>
            </div>
          )}

          {error && (
            <div className="flex items-start gap-2 p-3 bg-red-50 border border-red-200 rounded-lg">
              <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
              <p className="text-sm text-red-700">{error}</p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input bar */}
        <Card className="flex-shrink-0 border-gray-200 shadow-sm">
          <CardContent className="p-3">
            <div className="flex items-end gap-2">
              <textarea
                ref={textareaRef}
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about flight test standards, requirements, procedures… (Enter to send, Shift+Enter for new line)"
                rows={2}
                className="flex-1 resize-none border-0 outline-none text-sm text-gray-800 placeholder-gray-400 bg-transparent leading-relaxed"
              />
              <Button
                onClick={handleSubmit}
                disabled={!question.trim() || loading}
                className="bg-purple-600 hover:bg-purple-700 text-white flex-shrink-0 h-9 w-9 p-0"
              >
                {loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </Sidebar>
  );
}
