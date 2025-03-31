/**
 * 型定義のエクスポート
 */

// API共通型
export * from './api';

// 書籍関連
export * from './book';

// 検索関連
export * from './search';

// チャット関連
export * from './chat';

// ユーザー関連
export * from './user';

// Cross Point関連
export * from './crossPoint';

/**
 * アプリケーション状態
 */
export interface AppState {
  isOnline: boolean;
  isInitialized: boolean;
  isLoading: boolean;
  error: string | null;
}

/**
 * サマリー生成進捗状態
 */
export interface SummaryProgressState {
  isActive: boolean;
  progress: number;
  current: number;
  total: number;
  currentBook: string;
  status: 'processing' | 'completed' | 'error';
}

/**
 * トースト通知タイプ
 */
export type ToastType = 'info' | 'success' | 'warning' | 'error';

/**
 * トースト通知
 */
export interface Toast {
  id: string;
  type: ToastType;
  message: string;
  duration?: number;
}
