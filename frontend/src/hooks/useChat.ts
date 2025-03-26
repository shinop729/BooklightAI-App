import { useState, useCallback, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import axios from 'axios';
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
    
    // ストリーミングモードでの処理
    const tryStreamingMode = async () => {
      try {
        console.log('ストリーミングモードでリクエスト送信');
        
        // 開発環境かどうかを確認
        const isDevelopment = import.meta.env.DEV;
        console.log('環境情報:', { isDevelopment, baseURL: apiClient.defaults.baseURL });
        
        // fetchを使用してリクエストを送信（axiosはストリーミングに対応していないため）
        const headers: Record<string, string> = {
          'Content-Type': 'application/json',
        };
        
        console.log('チャットリクエスト:', JSON.stringify(chatRequest, null, 2));
        
        // 開発環境では固定トークンを使用
        if (isDevelopment) {
          // 開発環境でのトークン設定を確認
          const storedToken = localStorage.getItem('token');
          console.log('開発環境: localStorage内のトークン:', storedToken);
          
          // 常に固定トークンを使用
          headers['Authorization'] = `Bearer dev-token-123`;
          console.log('開発環境: 固定トークンをヘッダーに設定しました');
          
          // localStorage内のトークンが開発用トークンと異なる場合は更新
          if (storedToken !== 'dev-token-123') {
            console.log('開発環境: localStorage内のトークンを更新します');
            localStorage.setItem('token', 'dev-token-123');
          }
        } else {
          // 本番環境では保存されたトークンを使用
          const token = localStorage.getItem('token');
          if (token) {
            headers['Authorization'] = `Bearer ${token}`;
            console.log('本番環境: 保存されたトークンをヘッダーに設定しました');
          } else {
            console.warn('本番環境: トークンが見つかりません');
          }
        }

        console.log('ヘッダー情報:', headers);
        
        // fetchを使用してリクエストを送信（axiosはストリーミングに対応していないため）
        // ガイドラインに従ってポート番号を固定
        const baseURL = 'http://localhost:8000';
        const apiPrefix = '/api';
        const fullUrl = `${baseURL}${apiPrefix}/chat`; // 正しいエンドポイント
        
        console.log('リクエスト先URL:', fullUrl);
        console.log('リクエスト本文:', JSON.stringify(chatRequest, null, 2));
        console.log('ヘッダー情報:', JSON.stringify(headers, null, 2));
        
        // fetchを使用してストリーミングリクエストを送信
        const response = await fetch(fullUrl, {
          method: 'POST',
          headers,
          body: JSON.stringify(chatRequest),
          signal: controller.signal,
          credentials: 'include',  // クッキーを含める
          mode: 'cors'  // CORSモードを明示的に指定
        });
        
        console.log('レスポンス受信:', {
          status: response.status,
          statusText: response.statusText,
          headers: Object.fromEntries([...response.headers.entries()])
        });
        
        // エラーレスポンスの処理
        if (!response.ok) {
          // レスポンスの詳細情報をログに出力
          console.error('APIエラーレスポンス:', {
            status: response.status,
            statusText: response.statusText,
            headers: Object.fromEntries([...response.headers.entries()]),
          });
          
          // JSONレスポンスの取得を試みる
          try {
            const errorData = await response.json();
            console.error('APIエラー詳細:', errorData);
            throw new Error(errorData.message || errorData.error || `API error: ${response.status}`);
          } catch (jsonError) {
            // JSONとして解析できない場合はステータスコードのみ
            console.error('JSONパースエラー:', jsonError);
            throw new Error(`API error: ${response.status} ${response.statusText}`);
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
            messageId: aiMessageId,
            contentLength: accumulatedContent.length,
            contentPreview: accumulatedContent.substring(0, 50) + (accumulatedContent.length > 50 ? '...' : '')
          });
          
          updateMessage(aiMessageId, {
            content: accumulatedContent,
            isStreaming: !done
          });
          
          // 更新後のメッセージを確認
          const updatedSession = useChatStore.getState().sessions.find(s => s.id === currentSessionId);
          const updatedMessage = updatedSession?.messages.find(m => m.id === aiMessageId);
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
          messageId: aiMessageId, 
          contentLength: accumulatedContent.length,
          contentPreview: accumulatedContent.substring(0, 50) + (accumulatedContent.length > 50 ? '...' : ''),
          sourcesCount: sources.length 
        });
        
        // 最終更新 - 空の場合は空文字列を使用し、sourcesも明示的に空配列を設定
        // 内容が確実に存在することを確認
        const finalContent = accumulatedContent.trim() ? accumulatedContent : "メッセージを受信できませんでした。";
        
        // 最終更新を3回試行（信頼性向上のため）
        for (let attempt = 0; attempt < 3; attempt++) {
          console.log(`最終メッセージ更新 試行 ${attempt + 1}/3`);
          
          updateMessage(aiMessageId, {
            content: finalContent,
            isStreaming: false,
            sources: sources || []
          });
          
          // 更新後の状態を確認（同期的に実行）
          const currentState = useChatStore.getState();
          const currentSession = currentState.sessions.find(s => s.id === currentSessionId);
          const currentMsg = currentSession?.messages.find(m => m.id === aiMessageId);
          
          console.log(`更新確認 試行 ${attempt + 1}/3:`, {
            found: !!currentMsg,
            contentLength: currentMsg?.content?.length || 0,
            isStreaming: currentMsg?.isStreaming,
            sourcesCount: currentMsg?.sources?.length || 0
          });
          
          // 更新が成功していれば終了
          if (currentMsg && currentMsg.content && currentMsg.content.length > 0) {
            console.log('メッセージ更新成功');
            break;
          }
          
          // 失敗した場合は少し待機してから再試行
          if (attempt < 2) {
            console.warn('メッセージ更新失敗、再試行します');
            await new Promise(resolve => setTimeout(resolve, 50));
          }
        }
        
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
        
        // 開発環境かどうかを確認
        const isDevelopment = import.meta.env.DEV;
        
        // 開発環境では固定トークンを使用
        if (isDevelopment) {
          // localStorage内のトークンが開発用トークンと異なる場合は更新
          const storedToken = localStorage.getItem('token');
          if (storedToken !== 'dev-token-123') {
            console.log('非ストリーミングモード: 開発環境でトークンを更新します');
            localStorage.setItem('token', 'dev-token-123');
          }
        }
        
        console.log('非ストリーミングモード: リクエスト =', JSON.stringify(nonStreamingRequest, null, 2));
        
        // apiClientを使用してリクエストを送信
        // apiClientのbaseURLを確認
        console.log('apiClient baseURL:', apiClient.defaults.baseURL);
        
        // 直接エンドポイントを指定
        const response = await apiClient.post('http://localhost:8000/api/chat', nonStreamingRequest);
        console.log('非ストリーミングモード: レスポンス =', response.status, response.statusText);
        
        if (response.data.success) {
          const aiResponse = response.data.data.message.content;
          const sources = response.data.data.sources || [];
          
          console.log('非ストリーミングレスポンス内容:', {
            contentLength: aiResponse?.length || 0,
            contentPreview: aiResponse?.substring(0, 50) + (aiResponse?.length > 50 ? '...' : ''),
            sourcesCount: sources.length
          });
          
          updateMessage(aiMessageId, {
            content: aiResponse || "",
            isStreaming: false,
            sources: sources || []
          });
          
          return true; // 非ストリーミング成功
        } else {
          console.error('非ストリーミングエラーレスポンス:', response.data);
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
        updateMessage(aiMessageId, {
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
