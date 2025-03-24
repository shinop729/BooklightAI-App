import { ApiResponse, PaginatedResponse } from './api';

/**
 * 書籍情報
 */
export interface Book {
  id: string;
  title: string;
  author: string;
  summary?: string;
  highlightCount: number;
  coverUrl?: string;
  createdAt?: string;
  updatedAt?: string;
}

/**
 * ハイライト情報
 */
export interface Highlight {
  id: string;
  bookId: string;
  content: string;
  location?: string;
  createdAt?: string;
  updatedAt?: string;
}

/**
 * 書籍一覧レスポンス
 */
export type BooksResponse = ApiResponse<Book[]>;

/**
 * ページネーション付き書籍一覧データ
 */
export interface PaginatedBooks {
  items: Book[];
  total: number;
  total_pages: number;
  page: number;
  page_size: number;
}

/**
 * ページネーション付き書籍一覧レスポンス
 */
export type PaginatedBooksResponse = ApiResponse<PaginatedBooks>;

/**
 * 書籍詳細レスポンス
 */
export type BookResponse = ApiResponse<Book>;

/**
 * 書籍ハイライト一覧レスポンス
 */
export type BookHighlightsResponse = ApiResponse<Highlight[]>;

/**
 * 書籍カバー画像レスポンス
 */
export interface BookCoverResponse extends ApiResponse<{
  coverUrl: string;
}> {}

/**
 * 書籍サマリー生成リクエスト
 */
export interface GenerateSummaryRequest {
  bookId: string;
}

/**
 * 書籍サマリー生成レスポンス
 */
export interface GenerateSummaryResponse extends ApiResponse<{
  summary: string;
}> {}
