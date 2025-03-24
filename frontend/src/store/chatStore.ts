import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { ChatMessage } from '../hooks/useChat';

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
  addMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
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
        const id = Date.now().toString();
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
        
        set({
          sessions: sessions.map(session => 
            session.id === currentSessionId
              ? {
                  ...session,
                  messages: [
                    ...session.messages,
                    {
                      ...message,
                      id: Date.now().toString(),
                      timestamp: Date.now()
                    }
                  ],
                  updatedAt: Date.now()
                }
              : session
          )
        });
      },
      
      updateMessage: (id, updates) => {
        const { currentSessionId, sessions } = get();
        if (!currentSessionId) return;
        
        set({
          sessions: sessions.map(session => 
            session.id === currentSessionId
              ? {
                  ...session,
                  messages: session.messages.map(msg => 
                    msg.id === id ? { ...msg, ...updates } : msg
                  ),
                  updatedAt: Date.now()
                }
              : session
          )
        });
      },
      
      deleteSession: (id) => {
        const { currentSessionId, sessions } = get();
        
        set({
          sessions: sessions.filter(session => session.id !== id),
          currentSessionId: currentSessionId === id
            ? sessions.length > 1
              ? sessions.find(s => s.id !== id)?.id || null
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
