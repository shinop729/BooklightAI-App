import { create } from 'zustand';

interface SummaryProgressState {
  isActive: boolean;
  progress: number;
  current: number;
  total: number;
  currentBook: string;
  status: 'processing' | 'completed' | 'error';
  
  // アクション
  setProgress: (progress: number) => void;
  setCurrentBook: (book: string) => void;
  setStatus: (status: 'processing' | 'completed' | 'error') => void;
  reset: () => void;
  startProgress: (total: number) => void;
  incrementProgress: () => void;
  completeProgress: () => void;
  setError: () => void;
}

export const useSummaryProgressStore = create<SummaryProgressState>((set) => ({
  isActive: false,
  progress: 0,
  current: 0,
  total: 0,
  currentBook: '',
  status: 'processing',
  
  setProgress: (progress) => set({ progress }),
  setCurrentBook: (currentBook) => set({ currentBook }),
  setStatus: (status) => set({ status }),
  
  reset: () => set({
    isActive: false,
    progress: 0,
    current: 0,
    total: 0,
    currentBook: '',
    status: 'processing'
  }),
  
  startProgress: (total) => set({
    isActive: true,
    progress: 0,
    current: 0,
    total,
    status: 'processing'
  }),
  
  incrementProgress: () => set((state) => {
    const current = state.current + 1;
    const progress = state.total > 0 ? current / state.total : 0;
    return { current, progress };
  }),
  
  completeProgress: () => set({
    progress: 1,
    status: 'completed'
  }),
  
  setError: () => set({
    status: 'error'
  })
}));
