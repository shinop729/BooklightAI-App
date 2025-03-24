import { useState, useRef, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { useChat } from '../hooks/useChat';
import { ChatMessage, ChatSource } from '../types';

// 引用ソースコンポーネント
const SourceItem = ({ source }: { source: ChatSource }) => {
  return (
    <div className="bg-gray-700 rounded-lg p-3 mb-2">
      <div className="flex justify-between items-start mb-2">
        <div>
          <h4 className="text-white font-medium">{source.title}</h4>
          <p className="text-gray-400 text-sm">{source.author}</p>
        </div>
        {source.book_id && (
          <Link
            to={`/books/${encodeURIComponent(source.title)}`}
            className="text-blue-400 hover:text-blue-300 text-xs"
          >
            書籍を見る
          </Link>
        )}
      </div>
      <blockquote className="border-l-2 border-blue-500 pl-3 text-gray-300 text-sm">
        {source.content}
      </blockquote>
      {source.location && (
        <div className="text-gray-500 text-xs mt-1">位置: {source.location}</div>
      )}
    </div>
  );
};

// チャットセッション選択コンポーネント
const SessionSelector = ({ 
  sessions, 
  currentSessionId, 
  onSelect, 
  onNew 
}: { 
  sessions: any[],
  currentSessionId: string | null,
  onSelect: (id: string) => void,
  onNew: () => void
}) => {
  if (sessions.length <= 1) return null;
  
  return (
    <div className="mb-4">
      <div className="flex items-center gap-2 mb-2">
        <h3 className="text-white font-medium">会話履歴</h3>
        <button
          onClick={onNew}
          className="text-blue-400 hover:text-blue-300 text-sm"
        >
          新しい会話を開始
        </button>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-2">
        {sessions.map(session => (
          <button
            key={session.id}
            onClick={() => onSelect(session.id)}
            className={`px-3 py-1 rounded-full text-sm whitespace-nowrap ${
              session.id === currentSessionId
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
          >
            {session.title}
          </button>
        ))}
      </div>
    </div>
  );
};

const Chat = () => {
  const [searchParams] = useSearchParams();
  const bookParam = searchParams.get('book');
  const [inputValue, setInputValue] = useState('');
  const [showSources, setShowSources] = useState<Record<string, boolean>>({});
  
  const { 
    messages, 
    sendMessage, 
    isLoading, 
    error, 
    sessions,
    currentSessionId,
    selectSession,
    startNewChat,
    bookTitle
  } = useChat();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // メッセージ送信
  const handleSendMessage = async () => {
    if (inputValue.trim() && !isLoading) {
      await sendMessage(inputValue);
      setInputValue('');
    }
  };

  // Enterキーでメッセージ送信（Shift+Enterは改行）
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  };

  // 引用ソースの表示切り替え
  const toggleSources = (messageId: string) => {
    setShowSources(prev => ({
      ...prev,
      [messageId]: !prev[messageId]
    }));
  };
  
  // 新しいメッセージが追加されたら自動スクロール
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="flex flex-col h-[calc(100vh-64px)]">
      {/* メッセージ表示エリア */}
      <div className="flex-1 overflow-y-auto p-4 bg-gray-900">
        <div className="max-w-3xl mx-auto">
          {/* 書籍コンテキスト表示 */}
          {bookTitle && (
            <div className="bg-gray-800 rounded-lg p-3 mb-4 border-l-4 border-blue-500">
              <div className="flex items-center">
                <span className="text-blue-400 mr-2">📚</span>
                <span className="text-white">
                  「{bookTitle}」についてのチャット
                </span>
              </div>
            </div>
          )}
          
          {/* セッション選択 */}
          <SessionSelector
            sessions={sessions}
            currentSessionId={currentSessionId}
            onSelect={selectSession}
            onNew={startNewChat}
          />
          
          {/* メッセージ一覧 */}
          <div className="space-y-4">
            {messages.length === 0 ? (
              <div className="text-center py-8">
                <h2 className="text-xl font-semibold text-white mb-2">AIアシスタントとチャット</h2>
                <p className="text-gray-400">
                  あなたのハイライトに基づいて質問や相談ができます。<br />
                  例: 「リーダーシップについて教えて」「この本の要点は？」
                </p>
              </div>
            ) : (
              messages.map((message: ChatMessage) => (
                <div key={message.id}>
                  <div
                    className={`flex ${
                      message.role === 'user' ? 'justify-end' : 'justify-start'
                    }`}
                  >
                    <div
                      className={`max-w-[80%] rounded-lg p-4 ${
                        message.role === 'user'
                          ? 'bg-blue-600 text-white'
                          : 'bg-gray-800 text-white'
                      }`}
                    >
                      <div className="whitespace-pre-wrap">{message.content}</div>
                      <div className="flex justify-between items-center mt-2">
                        <div
                          className={`text-xs ${
                            message.role === 'user' ? 'text-blue-200' : 'text-gray-400'
                          }`}
                        >
                          {new Date(message.timestamp).toLocaleTimeString()}
                        </div>
                        
                        {/* 引用ソースボタン */}
                        {message.role === 'assistant' && message.sources && message.sources.length > 0 && (
                          <button
                            onClick={() => toggleSources(message.id)}
                            className="text-gray-400 hover:text-gray-300 text-xs ml-2"
                          >
                            {showSources[message.id] ? '引用元を隠す' : `引用元を表示 (${message.sources.length})`}
                          </button>
                        )}
                      </div>
                    </div>
                  </div>
                  
                  {/* 引用ソース表示 */}
                  {message.role === 'assistant' && 
                   message.sources && 
                   message.sources.length > 0 && 
                   showSources[message.id] && (
                    <div className="mt-2 ml-4 space-y-2">
                      <h4 className="text-gray-400 text-sm mb-1">引用元:</h4>
                      {message.sources.map((source, index) => (
                        <SourceItem key={index} source={source} />
                      ))}
                    </div>
                  )}
                </div>
              ))
            )}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-800 text-white rounded-lg p-4 max-w-[80%]">
                  <div className="flex space-x-2">
                    <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce"></div>
                    <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                    <div className="w-2 h-2 rounded-full bg-gray-500 animate-bounce" style={{ animationDelay: '0.4s' }}></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>
        </div>
      </div>

      {/* 入力エリア */}
      <div className="p-4 bg-gray-800 border-t border-gray-700">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-end gap-2">
            <textarea
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="メッセージを入力..."
              className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg resize-none min-h-[60px] max-h-[200px] focus:outline-none focus:ring-2 focus:ring-blue-500"
              rows={1}
            />
            <button
              onClick={handleSendMessage}
              disabled={isLoading || !inputValue.trim()}
              className="bg-blue-600 hover:bg-blue-700 text-white p-3 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5"
                viewBox="0 0 20 20"
                fill="currentColor"
              >
                <path
                  fillRule="evenodd"
                  d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-8.707l-3-3a1 1 0 00-1.414 0l-3 3a1 1 0 001.414 1.414L9 9.414V13a1 1 0 102 0V9.414l1.293 1.293a1 1 0 001.414-1.414z"
                  clipRule="evenodd"
                />
              </svg>
            </button>
          </div>
          {error && (
            <div className="mt-2 text-red-500 text-sm">
              エラーが発生しました。もう一度お試しください。
            </div>
          )}
          <div className="mt-2 text-gray-400 text-xs">
            Shift+Enterで改行、Enterで送信
          </div>
        </div>
      </div>
    </div>
  );
};

export default Chat;
