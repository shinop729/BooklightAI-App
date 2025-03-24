import { ApiResponse } from './api';

/**
 * 検索結果のドキュメント
 */
export interface SearchDocument {
  page_content: string;
  metadata: {
    original_title: string;
    original_author: string;
    book_id?: string;
    location?: string;
    created_at?: string;
  };
}

/**
 * 検索結果アイテム
 */
export interface SearchResult {
  doc: SearchDocument;
  score: number;
}

/**
 * 検索リクエストパラメータ
 */
export interface SearchRequest {
  keywords: string[];
  hybrid_alpha?: number; // ベクトル検索とキーワード検索の重み付け (0-1)
  book_weight?: number; // 書籍タイトル/著者の重み付け (0-1)
  use_expanded?: boolean; // 拡張検索を使用するかどうか
  limit?: number; // 結果の最大数
}

/**
 * 検索レスポンス
 */
export interface SearchResponse extends ApiResponse<{
  results: SearchResult[];
  query_time_ms?: number;
}> {}

/**
 * 検索サジェストレスポンス
 */
export interface SearchSuggestResponse extends ApiResponse<{
  suggestions: string[];
}> {}

/**
 * 検索履歴アイテム
 */
export interface SearchHistoryItem {
  id: string;
  keywords: string[];
  timestamp: string;
  result_count: number;
}

/**
 * 検索履歴レスポンス
 */
export interface SearchHistoryResponse extends ApiResponse<{
  history: SearchHistoryItem[];
}> {}
