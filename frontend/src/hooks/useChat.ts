import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import apiClient from '../api/client';
import { ChatMessage, ChatRequest, ChatRole, ChatSource } from '../types';
import { useChatStore } from '../store/chatStore';

interface UseChatOptions {
  bookTitle?: string;
  sessionId?: string;
}

export const useChat = (options: UseChatOptions = {}) => {
  const [searchParams] = useSearchParams();
  const bookParam = searchParams.get('book');
  const bookTitle = options.bookTitle || bookParam || undefined;
  
  // チャットストアからの状態と操作
  const {
    sessions,
    currentSessionId,
    createSession,
    selectSession,
    addMessage,
    updateMessage,
    deleteSession
  } = useChatStore();
  
  // ローカル状態
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);
  
  // 現在のセッションのメッセージ
  const currentSession = sessions.find(s => s.id === currentSessionId);
  const messages = currentSession?.messages || [];
  
  // セッションの初期化
  useEffect(() => {
    // セッションIDが指定されている場合はそれを選択
    if (options.sessionId) {
      const sessionExists = sessions.some(s => s.id === options.sessionId);
      if (sessionExists) {
        selectSession(options.sessionId);
      } else {
        // 存在しない場合は新しいセッションを作成
        createSession(bookTitle ? `${bookTitle}について` : undefined);
      }
    } else if (!currentSessionId) {
      // 現在のセッションがない場合は新しいセッションを作成
      createSession(bookTitle ? `${bookTitle}について` : undefined);
    }
  }, [options.sessionId, bookTitle, currentSessionId, sessions, createSession, selectSession]);
  
  // システムメッセージの作成
  const createSystemMessage = useCallback(() => {
    if (!bookTitle) return null;
    
    return {
      role: 'system' as ChatRole,
      content: `ユーザーは「${bookTitle}」という本について質問しています。この本に関連する情報を中心に回答してください。`
    };
  }, [bookTitle]);

  const sendMessage = useCallback(async (content: string) => {
    if (!currentSessionId) {
      setError('チャットセッションが初期化されていません');
      return;
    }
    setIsLoading(true);
    setError(null);
    
    // 新しいメッセージを追加
    const userMessage: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'user',
      content,
      timestamp: Date.now()
    };
    addMessage(userMessage);
    
    // AIの応答用プレースホルダー
    const aiMessage: ChatMessage = {
      id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true
    };
    addMessage(aiMessage);
    
    // AbortControllerの設定
    const controller = new AbortController();
    setAbortController(controller);
    
    try {
      // チャットリクエストの作成
      const systemMessage = createSystemMessage();
      const chatMessages = messages.slice(0, -1); // 最後のAIメッセージを除外
      
      const requestMessages = [
        ...(systemMessage ? [systemMessage] : []),
        ...chatMessages.map(m => ({
          role: m.role as ChatRole,
          content: m.content
        })),
        {
          role: userMessage.role as ChatRole,
          content: userMessage.content
        }
      ];
      
      const chatRequest: ChatRequest = {
        messages: requestMessages,
        stream: true,
        use_sources: true
      };
      
      const response = await fetch(`${apiClient.defaults.baseURL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(chatRequest),
        signal: controller.signal
      });
      
      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }
      
      // ストリーミングレスポンスの処理
      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }
      
      const decoder = new TextDecoder();
      let done = false;
      let accumulatedContent = '';
      
      while (!done) {
        const { value, done: doneReading } = await reader.read();
        done = doneReading;
        
        if (done) break;
        
        const chunk = decoder.decode(value, { stream: true });
        accumulatedContent += chunk;
        
        // メッセージを更新
        updateMessage(aiMessage.id, {
          content: accumulatedContent,
          isStreaming: !done
        });
      }
      
      // ストリーミング完了
      // ソース情報の取得と型変換
      let sources: ChatSource[] = [];
      try {
        const sourcesHeader = response.headers.get('X-Sources');
        if (sourcesHeader) {
          sources = JSON.parse(sourcesHeader) as ChatSource[];
        }
      } catch (e) {
        console.error('Failed to parse sources:', e);
      }
      
      updateMessage(aiMessage.id, {
        content: accumulatedContent,
        isStreaming: false,
        sources
      });
      
    } catch (e) {
      if (e instanceof Error) {
        if (e.name !== 'AbortError') {
          setError(e.message);
          // エラーメッセージを表示
          updateMessage(aiMessage.id, {
            content: `エラーが発生しました: ${e.message}`,
            isError: true,
            isStreaming: false
          });
        }
      }
    } finally {
      setIsLoading(false);
      setAbortController(null);
    }
  }, [currentSessionId, messages, addMessage, updateMessage, createSystemMessage]);
  
  // チャットのキャンセル
  const cancelChat = useCallback(() => {
    if (abortController) {
      abortController.abort();
      setIsLoading(false);
      
      // ストリーミング中のメッセージを更新
      if (messages.length > 0) {
        const lastMessage = messages[messages.length - 1];
        if (lastMessage.isStreaming) {
          updateMessage(lastMessage.id, {
            content: lastMessage.content + ' (キャンセルされました)',
            isStreaming: false
          });
        }
      }
    }
  }, [abortController, messages, updateMessage]);
  
  // 会話履歴のクリア
  const clearChat = useCallback(() => {
    if (currentSessionId) {
      deleteSession(currentSessionId);
      createSession(bookTitle ? `${bookTitle}について` : undefined);
    }
  }, [currentSessionId, bookTitle, deleteSession, createSession]);
  
  // 新しいチャットの開始
  const startNewChat = useCallback(() => {
    createSession(bookTitle ? `${bookTitle}について` : undefined);
  }, [bookTitle, createSession]);
  
  return {
    messages,
    isLoading,
    error,
    sendMessage,
    cancelChat,
    clearChat,
    startNewChat,
    currentSessionId,
    sessions,
    selectSession,
    bookTitle
  };
};
