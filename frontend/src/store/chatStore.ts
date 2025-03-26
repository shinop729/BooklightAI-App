import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ChatMessage } from '../types/chat';

interface ChatSession {
  id: string;
  title: string;
  messages: ChatMessage[];
  createdAt: number;
  updatedAt: number;
}

interface ChatStore {
  sessions: ChatSession[];
  currentSessionId: string | null;
  
  // アクション
  createSession: (title?: string) => string;
  selectSession: (id: string) => void;
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => string | undefined;
  updateMessage: (id: string, updates: Partial<ChatMessage>) => void;
  deleteSession: (id: string) => void;
  clearSessions: () => void;
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get) => ({
      sessions: [],
      currentSessionId: null,
      
      createSession: (title = '新しい会話') => {
        const id = `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`;
        set(state => ({
          sessions: [
            ...state.sessions,
            {
              id,
              title,
              messages: [],
              createdAt: Date.now(),
              updatedAt: Date.now()
            }
          ],
          currentSessionId: id
        }));
        return id;
      },
      
      selectSession: (id) => {
        set({ currentSessionId: id });
      },
      
      addMessage: (message) => {
        const { currentSessionId, sessions } = get();
        if (!currentSessionId) return;
        
        // 新しいメッセージを追加（不変性を保ちつつ更新）
        const newMessage = {
          ...message,
          id: `${message.role}-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
          timestamp: Date.now()
        };
        
        // セッションの配列を変更
        const updatedSessions = sessions.map(session => 
          session.id === currentSessionId
            ? {
                ...session,
                messages: [...session.messages, newMessage],
                updatedAt: Date.now()
              }
            : session
        );
        
        // 状態を更新
        set({
          sessions: updatedSessions
        });
        
        // デバッグログ
        console.log(`メッセージ追加: sessionId=${currentSessionId}, messageId=${newMessage.id}, role=${newMessage.role}`);
        
        return newMessage.id;
      },
      
      updateMessage: (id, updates) => {
        const { currentSessionId, sessions } = get();
        if (!currentSessionId) {
          console.error('現在のセッションIDがありません');
          return;
        }
        
        // 更新対象のセッションを見つける
        const sessionIndex = sessions.findIndex(s => s.id === currentSessionId);
        if (sessionIndex === -1) {
          console.error(`セッションが見つかりません: ${currentSessionId}`);
          return;
        }
        
        const session = sessions[sessionIndex];
        
        // 更新対象のメッセージを見つける
        const messageIndex = session.messages.findIndex(m => m.id === id);
        if (messageIndex === -1) {
          console.error(`メッセージが見つかりません: ${id}, セッション内のメッセージ数: ${session.messages.length}`);
          // セッション内のメッセージIDをログに出力
          console.log('セッション内のメッセージID:', session.messages.map(m => m.id));
          return;
        }
        
        // メッセージを更新
        const updatedMessage = {
          ...session.messages[messageIndex],
          ...updates
        };
        
        // 内容が空でないことを確認
        if (updates.content !== undefined && (!updates.content || updates.content === "undefined")) {
          console.warn(`空の内容で更新しようとしています: ${id}`);
          // 空の場合はデフォルトメッセージを設定
          updatedMessage.content = "メッセージを受信できませんでした";
        }
        
        // 新しいメッセージ配列を作成
        const updatedMessages = [...session.messages];
        updatedMessages[messageIndex] = updatedMessage;
        
        // 新しいセッション配列を作成
        const updatedSessions = [...sessions];
        updatedSessions[sessionIndex] = {
          ...session,
          messages: updatedMessages,
          updatedAt: Date.now()
        };
        
        // 状態を更新
        set({
          sessions: updatedSessions
        });
        
        // デバッグログ
        console.log(`メッセージ更新: sessionId=${currentSessionId}, messageId=${id}, contentLength=${updatedMessage.content?.length || 0}`);
        
        // 更新した状態の確認（同期的に実行）
        const currentState = get();
        const currentSession = currentState.sessions.find(s => s.id === currentSessionId);
        const currentMsg = currentSession?.messages.find(m => m.id === id);
        console.log(`更新確認: found=${!!currentMsg}, contentLength=${currentMsg?.content?.length || 0}`);
      },
      
      deleteSession: (id) => {
        const { currentSessionId, sessions } = get();
        
        const filteredSessions = sessions.filter(session => session.id !== id);
        
        set({
          sessions: filteredSessions,
          currentSessionId: currentSessionId === id
            ? filteredSessions.length > 0
              ? filteredSessions[0].id
              : null
            : currentSessionId
        });
      },
      
      clearSessions: () => {
        set({ sessions: [], currentSessionId: null });
      }
    }),
    {
      name: 'booklight-chat-storage',
      partialize: (state) => ({
        sessions: state.sessions,
        currentSessionId: state.currentSessionId
      })
    }
  )
);
