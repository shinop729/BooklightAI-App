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
    console.log('sendMessage関数が呼び出されました', { content, sessionId: currentSessionId });
    if (!currentSessionId) {
      console.error('チャットセッションが初期化されていません');
      setError('チャットセッションが初期化されていません');
      return;
    }
    
    setIsLoading(true);
    setError(null);
    
    // ユーザーメッセージをストアに追加（UIに表示するため）
    console.log('ユーザーメッセージをストアに追加:', content);
    const userMessageData = {
      role: 'user' as ChatRole,
      content
    };
    addMessage(userMessageData);
    
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
    
    console.log('AIメッセージプレースホルダーを追加:', aiMessageId);
    
    // AbortControllerの設定
    const controller = new AbortController();
    setAbortController(controller);
    
    // チャットリクエストの作成（ストアを参照せず、直接構築）
    const systemMessage = createSystemMessage();
    
    // 現在のセッションのメッセージを取得（最新のAIプレースホルダーを除く）
    // 注意: ここでは最新のユーザーメッセージはまだストアに反映されていない可能性があるため
    // 直接contentを使用する
    const chatMessages = messages.filter(m => m.id !== aiMessageId);
    
    console.log('会話履歴を構築:', {
      messagesCount: chatMessages.length,
      hasSystemMessage: !!systemMessage
    });
    
    // リクエストメッセージの構築を簡素化
    const requestMessages = [
      ...(systemMessage ? [systemMessage] : []),
      ...chatMessages.map(m => ({
        role: m.role as ChatRole,
        content: m.content
      })),
      // 直接ユーザー入力を使用（ストアから取得しない）
      {
        role: 'user' as ChatRole,
        content
      }
    ];
    
    const chatRequest: ChatRequest = {
      messages: requestMessages,
      stream: true,
      use_sources: true
    };
    
    // エンドポイントの定義
    // API_URLは環境変数から取得するが、エンドポイントパスは常に/api/chatを使用
    const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
    
    console.log('APIリクエスト準備', {
      url: '/api/chat',
      isDev: import.meta.env.DEV,
      apiBaseUrl: API_URL
    });
    
    // DEV環境ではdev-token-123を使用することを確認
    if (import.meta.env.DEV) {
      // 開発環境では明示的に認証ヘッダーを設定
      apiClient.defaults.headers.common['Authorization'] = 'Bearer dev-token-123';
    }
    
    // リクエストパラメータのログ
    console.log('リクエスト内容:', {
      endpoint: '/api/chat',
      headers: apiClient.defaults.headers,
      requestBody: { ...chatRequest, stream: false } // 非ストリーミングモード用に設定
    });
    
    // 非ストリーミングモードで試行（優先的に使用）
    try {
      console.log('非ストリーミングモードでリクエスト送信');
      
      // リクエストパラメータのログ
      console.log('非ストリーミングリクエスト内容:', {
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
          
          // JSONパースに失敗した場合、レスポンスデータをそのまま使用
          if (typeof response.data === 'string' && response.data.trim()) {
            console.log('JSONパースに失敗したため、テキストとして処理します');
            aiResponse = response.data;
          } else {
            throw new Error('レスポンスの解析に失敗しました');
          }
        }
      } else {
        // プレーンテキストの場合
        console.log('テキストレスポンス:', response.data);
        aiResponse = response.data;
        
        // X-Sourcesヘッダーからsources情報を取得
        const sourcesHeader = response.headers['x-sources'];
        console.log('X-Sourcesヘッダー:', sourcesHeader);
        
        if (sourcesHeader) {
          try {
            sources = JSON.parse(sourcesHeader);
            console.log('X-Sourcesヘッダーから引用元情報を取得:', sources);
          } catch (parseError) {
            console.error('X-Sourcesヘッダーの解析エラー:', parseError);
          }
        }
      }
        
        // レスポンスが空の場合のデフォルトメッセージ
        if (!aiResponse || aiResponse.trim() === '') {
          aiResponse = "レスポンスが空でした。もう一度お試しください。";
        }
        
      // レスポンス内容をログ
      console.log('AIレスポンス:', {
        contentLength: aiResponse?.length || 0,
        sourcesCount: sources.length,
        sources: sources
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
