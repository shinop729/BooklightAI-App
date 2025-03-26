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
      id: `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'user',
      content,
      timestamp: Date.now()
    };
    addMessage(userMessage);
    
    // AIの応答用プレースホルダー
    const aiMessage: ChatMessage = {
      id: `assistant-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true
    };
    addMessage(aiMessage);
    
    // AbortControllerの設定
    const controller = new AbortController();
    setAbortController(controller);
    
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
    
    // ストリーミングモードでの処理
    const tryStreamingMode = async () => {
      try {
        console.log('ストリーミングモードでリクエスト送信');
        
        // 開発環境かどうかを確認
        const isDevelopment = import.meta.env.DEV;
        console.log('環境情報:', { isDevelopment, baseURL: apiClient.defaults.baseURL });
        
        // ヘッダーの設定（開発環境では認証トークンをデフォルト値に）
        const headers: Record<string, string> = {
          'Content-Type': 'application/json'
        };
        
        // 認証トークンの取得
        const token = localStorage.getItem('token');
        console.log('認証トークン:', { token: token ? '存在します' : 'ありません' });
        
        // 開発環境では固定トークンを使用、本番環境では通常のトークンを使用
        if (isDevelopment) {
          headers['Authorization'] = 'Bearer dev-token-123'; // 開発環境用の固定トークン
        } else if (token) {
          headers['Authorization'] = `Bearer ${token}`;
        }
        
        // apiClientを使用してリクエストを送信
        const response = await fetch(`${apiClient.defaults.baseURL}/api/chat`, {
          method: 'POST',
          headers,
          body: JSON.stringify(chatRequest),
          signal: controller.signal
        });
        
        // エラーレスポンスの処理
        if (!response.ok) {
          // JSONレスポンスの取得を試みる
          try {
            const errorData = await response.json();
            throw new Error(errorData.message || errorData.error || `API error: ${response.status}`);
          } catch (jsonError) {
            // JSONとして解析できない場合はステータスコードのみ
            throw new Error(`API error: ${response.status}`);
          }
        }
        
        // ストリーミングレスポンスの処理
        const reader = response.body?.getReader();
        if (!reader) {
          throw new Error('Response body is not readable');
        }
        
        console.log('ストリーミングレスポンス処理開始', { 
          status: response.status,
          headers: Object.fromEntries([...response.headers.entries()]),
        });
        
        const decoder = new TextDecoder();
        let done = false;
        let accumulatedContent = '';
        
        while (!done) {
          const { value, done: doneReading } = await reader.read();
          done = doneReading;
          
          if (done) {
            console.log('ストリーミング読み取り完了');
            break;
          }
          
          const chunk = decoder.decode(value, { stream: true });
          console.log('チャンク受信:', { 
            chunkLength: chunk.length, 
            chunk: chunk.substring(0, 50) + (chunk.length > 50 ? '...' : ''),
            rawChunk: value ? Array.from(value).map(b => b.toString(16).padStart(2, '0')).join(' ') : 'undefined'
          });
          
          // 空のチャンクをスキップ
          if (chunk.trim().length === 0) {
            console.log('空のチャンクをスキップ');
            continue;
          }
          
          accumulatedContent += chunk;
          
          // メッセージを更新
          console.log('メッセージ更新（チャンク受信時）:', {
            messageId: aiMessage.id,
            contentLength: accumulatedContent.length,
            contentPreview: accumulatedContent.substring(0, 50) + (accumulatedContent.length > 50 ? '...' : '')
          });
          
          updateMessage(aiMessage.id, {
            content: accumulatedContent,
            isStreaming: !done
          });
          
          // 更新後のメッセージを確認
          const updatedSession = useChatStore.getState().sessions.find(s => s.id === currentSessionId);
          const updatedMessage = updatedSession?.messages.find(m => m.id === aiMessage.id);
          console.log('更新後のメッセージ状態:', {
            found: !!updatedMessage,
            content: updatedMessage?.content?.substring(0, 50) + (updatedMessage?.content && updatedMessage.content.length > 50 ? '...' : ''),
            contentLength: updatedMessage?.content?.length || 0,
            isStreaming: updatedMessage?.isStreaming
          });
        }
        
        // ストリーミング完了
        console.log('ストリーミング完了、ヘッダー情報取得');
        
        // ソース情報の取得と型変換
        let sources: ChatSource[] = [];
        try {
          const sourcesHeader = response.headers.get('X-Sources');
          console.log('X-Sourcesヘッダー:', sourcesHeader);
          
          if (sourcesHeader) {
            sources = JSON.parse(sourcesHeader) as ChatSource[];
            console.log('パース済みソース情報:', sources);
          } else {
            console.warn('X-Sourcesヘッダーが見つかりません');
            
            // ヘッダーが見つからない場合は空の配列を使用
            sources = [];
          }
        } catch (e) {
          console.error('ソース情報のパースに失敗:', e);
          // エラー時は空の配列を使用
          sources = [];
        }
        
        // 最終的なコンテンツが空でないことを確認
        if (!accumulatedContent.trim()) {
          console.warn('空のレスポンスを検出、デフォルトメッセージを使用');
          accumulatedContent = "申し訳ありません。レスポンスを取得できませんでした。もう一度お試しください。";
        }
        
        console.log('最終メッセージ更新', { 
          messageId: aiMessage.id, 
          contentLength: accumulatedContent.length,
          contentPreview: accumulatedContent.substring(0, 50) + (accumulatedContent.length > 50 ? '...' : ''),
          sourcesCount: sources.length 
        });
        
        // 最終更新
        updateMessage(aiMessage.id, {
          content: accumulatedContent,
          isStreaming: false,
          sources
        });
        
        // 更新後の最終状態を確認
        const finalSession = useChatStore.getState().sessions.find(s => s.id === currentSessionId);
        const finalMessage = finalSession?.messages.find(m => m.id === aiMessage.id);
        console.log('最終メッセージ状態:', {
          found: !!finalMessage,
          content: finalMessage?.content?.substring(0, 50) + (finalMessage?.content && finalMessage.content.length > 50 ? '...' : ''),
          contentLength: finalMessage?.content?.length || 0,
          isStreaming: finalMessage?.isStreaming,
          sourcesCount: finalMessage?.sources?.length || 0
        });
        
        return true; // ストリーミング成功
      } catch (e) {
        if (e instanceof Error) {
          if (e.name === 'AbortError') {
            console.log('リクエストがキャンセルされました');
            return false; // キャンセルされた場合は失敗とみなさない
          }
          console.error('ストリーミングモードエラー:', e);
          throw e; // 再スロー
        }
        return false;
      }
    };
    
    // 非ストリーミングモードでの処理（フォールバック）
    const tryNonStreamingMode = async () => {
      try {
        console.log('非ストリーミングモードでリクエスト送信（フォールバック）');
        
        // 非ストリーミングリクエストの作成
        const nonStreamingRequest: ChatRequest = {
          ...chatRequest,
          stream: false
        };
        
        // apiClientを使用してリクエストを送信
        const response = await apiClient.post('/api/chat', nonStreamingRequest);
        
        if (response.data.success) {
          const aiResponse = response.data.data.message.content;
          const sources = response.data.data.sources || [];
          
          updateMessage(aiMessage.id, {
            content: aiResponse,
            isStreaming: false,
            sources
          });
          
          return true; // 非ストリーミング成功
        } else {
          throw new Error(response.data.error || response.data.message || '不明なエラー');
        }
      } catch (e) {
        console.error('非ストリーミングモードエラー:', e);
        throw e; // 再スロー
      }
    };
    
    try {
      // まずストリーミングモードを試す
      const streamingSuccess = await tryStreamingMode();
      
      // ストリーミングが失敗した場合、非ストリーミングモードを試す
      if (!streamingSuccess && !controller.signal.aborted) {
        await tryNonStreamingMode();
      }
    } catch (e) {
      if (e instanceof Error) {
        setError(e.message);
        // エラーメッセージを表示
        updateMessage(aiMessage.id, {
          content: `エラーが発生しました: ${e.message}`,
          isError: true,
          isStreaming: false
        });
        
        console.error('チャットエラー詳細:', e);
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
