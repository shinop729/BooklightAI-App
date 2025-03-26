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
    console.log('sendMessage関数が呼び出されました', { content });
    if (!currentSessionId) {
      console.error('チャットセッションが初期化されていません');
      setError('チャットセッションが初期化されていません');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    // 新しいメッセージを追加（IDはchatStoreで生成）
    const userMessageData = {
      role: 'user' as ChatRole,
      content
    };
    const userMessageId = addMessage(userMessageData);
    
    if (!userMessageId) {
      setError('メッセージの追加に失敗しました');
      setIsLoading(false);
      return;
    }
    
    // AIの応答用プレースホルダー（IDはchatStoreで生成）
    const aiMessageData = {
      role: 'assistant' as ChatRole,
      content: '',
      isStreaming: true
    };
    const aiMessageId = addMessage(aiMessageData);
    
    if (!aiMessageId) {
      setError('AIメッセージの追加に失敗しました');
      setIsLoading(false);
      return;
    }
    
    // AbortControllerの設定
    const controller = new AbortController();
    setAbortController(controller);
    
    // チャットリクエストの作成
    const systemMessage = createSystemMessage();
    const chatMessages = messages.slice(0, -1); // 最後のAIメッセージを除外
    
    // 最新のメッセージを取得
    const currentSession = sessions.find(s => s.id === currentSessionId);
    if (!currentSession) {
      setError('セッションが見つかりません');
      setIsLoading(false);
      return;
    }
    
    // ユーザーメッセージを取得
    const userMessage = currentSession.messages.find(m => m.id === userMessageId);
    if (!userMessage) {
      setError('ユーザーメッセージが見つかりません');
      setIsLoading(false);
      return;
    }
    
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
    
    // エンドポイントの定義
    // ここが重要: API_URLを環境変数から取得し、正しいエンドポイントパスを構築
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    const chatEndpoint = `${API_URL}/chat`;
    
    console.log('APIリクエスト準備', {
      url: chatEndpoint,
      isDev: import.meta.env.DEV,
      apiBaseUrl: API_URL
    });
    
    // 非ストリーミングモードで試行（従来のAPI使用）
    try {
      console.log('非ストリーミングモードでリクエスト送信');
      
      // DEV環境ではdev-token-123を使用することを確認
      if (import.meta.env.DEV) {
        // 開発環境では明示的に認証ヘッダーを設定
        apiClient.defaults.headers.common['Authorization'] = 'Bearer dev-token-123';
      }
      
      // リクエストパラメータのログ
      console.log('リクエスト内容:', {
        endpoint: '/api/chat',
        headers: apiClient.defaults.headers,
        requestBody: { ...chatRequest, stream: false }
      });
      
      try {
        // APIClientを使用してリクエストを送信
        console.log('APIリクエスト送信開始...');
        const response = await apiClient.post('/api/chat', {
          ...chatRequest,
          stream: false // 非ストリーミングモード
        }, {
          // レスポンスタイプを自動判別しない
          transformResponse: [(data) => data]
        });
        console.log('APIリクエスト送信完了');
        
        // Content-Typeヘッダーをチェック
        const contentType = response.headers['content-type'];
        console.log('レスポンスのContent-Type:', contentType);
        
        // レスポンスデータの処理
        let aiResponse = '';
        let sources: ChatSource[] = [];
        
        if (contentType && contentType.includes('application/json')) {
          // JSONレスポンスの場合
          try {
            const jsonData = JSON.parse(response.data);
            console.log('JSONレスポンスデータ:', jsonData);
            
            if (jsonData.success) {
              aiResponse = jsonData.data.message.content;
              sources = jsonData.data.sources || [];
            } else {
              throw new Error(jsonData.message || jsonData.error || '不明なエラー');
            }
          } catch (parseError) {
            console.error('JSONパースエラー:', parseError);
            throw new Error('レスポンスの解析に失敗しました');
          }
        } else {
          // プレーンテキストの場合
          console.log('テキストレスポンス:', response.data);
          aiResponse = response.data;
        }
        
        // レスポンス内容をログ
        console.log('AIレスポンス:', {
          contentLength: aiResponse?.length || 0,
          sourcesCount: sources.length
        });
        
        // メッセージを更新
        updateMessage(aiMessageId, {
          content: aiResponse || "レスポンスが空でした",
          isStreaming: false,
          sources: sources
        });
      } catch (innerError) {
        console.error('APIリクエスト送信中のエラー:', innerError);
        if (innerError instanceof Error) {
          console.error('エラーの詳細:', {
            name: innerError.name,
            message: innerError.message,
            stack: innerError.stack
          });
        }
        throw innerError; // 外側のcatchブロックで処理するためにエラーを再スロー
      }
    } catch (error) {
      console.error('チャット通信エラー:', error);
      let errorMessage = '通信エラーが発生しました';
      
      if (error instanceof Error) {
        errorMessage = `エラー: ${error.message}`;
        console.error('エラーの詳細:', {
          name: error.name,
          message: error.message,
          stack: error.stack
        });
      }
      
      // エラーメッセージを表示
      updateMessage(aiMessageId, {
        content: errorMessage,
        isError: true,
        isStreaming: false
      });
      
      setError(errorMessage);
    } finally {
      setIsLoading(false);
      setAbortController(null);
    }
  }, [currentSessionId, messages, addMessage, updateMessage, createSystemMessage, sessions]);
  
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
