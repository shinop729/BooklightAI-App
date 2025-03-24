import { ApiResponse } from './api';

/**
 * チャットメッセージの役割
 */
export type ChatRole = 'user' | 'assistant' | 'system';

/**
 * チャットメッセージ
 */
export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  timestamp: number;
  isStreaming?: boolean;
  isError?: boolean;
  sources?: ChatSource[];
}

/**
 * チャットソース（引用元）
 */
export interface ChatSource {
  book_id: string;
  title: string;
  author: string;
  content: string;
  location?: string;
  score?: number;
}

/**
 * チャットリクエスト
 */
export interface ChatRequest {
  messages: {
    role: ChatRole;
    content: string;
  }[];
  stream?: boolean;
  temperature?: number;
  max_tokens?: number;
  use_sources?: boolean;
}

/**
 * チャットレスポンス（非ストリーミング）
 */
export interface ChatResponse extends ApiResponse<{
  message: {
    role: 'assistant';
    content: string;
  };
  sources?: ChatSource[];
}> {}

/**
 * チャット履歴アイテム
 */
export interface ChatHistoryItem {
  id: string;
  title: string;
  last_message: string;
  message_count: number;
  created_at: string;
  updated_at: string;
}

/**
 * チャット履歴レスポンス
 */
export interface ChatHistoryResponse extends ApiResponse<{
  conversations: ChatHistoryItem[];
}> {}

/**
 * チャット会話詳細レスポンス
 */
export interface ChatConversationResponse extends ApiResponse<{
  id: string;
  title: string;
  messages: ChatMessage[];
  created_at: string;
  updated_at: string;
}> {}
