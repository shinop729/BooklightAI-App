import { useState, useCallback } from 'react';
import apiClient from '../api/client';
import { ChatMessage, ChatRequest, ChatRole, ChatSource } from '../types';

export const useChat = () => {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [abortController, setAbortController] = useState<AbortController | null>(null);

  const sendMessage = useCallback(async (content: string) => {
    setIsLoading(true);
    setError(null);
    
    // 新しいメッセージを追加
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      role: 'user',
      content,
      timestamp: Date.now()
    };
    setMessages(prev => [...prev, userMessage]);
    
    // AIの応答用プレースホルダー
    const aiMessage: ChatMessage = {
      id: (Date.now() + 1).toString(),
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true
    };
    setMessages(prev => [...prev, aiMessage]);
    
    // AbortControllerの設定
    const controller = new AbortController();
    setAbortController(controller);
    
    try {
      // チャットリクエストの作成
      const chatRequest: ChatRequest = {
        messages: messages.concat(userMessage).map(m => ({
          role: m.role as ChatRole,
          content: m.content
        })),
        stream: true
      };
      
      const response = await fetch(`${apiClient.defaults.baseURL}/api/v2/chat`, {
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
        setMessages(prev => {
          const newMessages = [...prev];
          const lastIndex = newMessages.length - 1;
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            content: accumulatedContent,
            isStreaming: !done
          };
          return newMessages;
        });
      }
      
      // ストリーミング完了
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        
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
        
        newMessages[lastIndex] = {
          ...newMessages[lastIndex],
          content: accumulatedContent,
          isStreaming: false,
          sources
        };
        return newMessages;
      });
      
    } catch (e) {
      if (e instanceof Error) {
        if (e.name !== 'AbortError') {
          setError(e.message);
          // エラーメッセージを表示
          setMessages(prev => {
            const newMessages = [...prev];
            const lastIndex = newMessages.length - 1;
            newMessages[lastIndex] = {
              ...newMessages[lastIndex],
              content: `エラーが発生しました: ${e.message}`,
              isError: true,
              isStreaming: false
            };
            return newMessages;
          });
        }
      }
    } finally {
      setIsLoading(false);
      setAbortController(null);
    }
  }, [messages]);
  
  // チャットのキャンセル
  const cancelChat = useCallback(() => {
    if (abortController) {
      abortController.abort();
      setIsLoading(false);
      
      // ストリーミング中のメッセージを更新
      setMessages(prev => {
        const newMessages = [...prev];
        const lastIndex = newMessages.length - 1;
        if (newMessages[lastIndex].isStreaming) {
          newMessages[lastIndex] = {
            ...newMessages[lastIndex],
            content: newMessages[lastIndex].content + ' (キャンセルされました)',
            isStreaming: false
          };
        }
        return newMessages;
      });
    }
  }, [abortController]);
  
  // 会話履歴のクリア
  const clearChat = useCallback(() => {
    setMessages([]);
  }, []);
  
  return {
    messages,
    isLoading,
    error,
    sendMessage,
    cancelChat,
    clearChat
  };
};
