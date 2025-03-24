import { ApiResponse } from './api';

/**
 * ユーザー情報
 */
export interface User {
  id: string;
  username: string;
  email: string;
  name: string;
  picture?: string;
  google_id?: string;
  disabled?: boolean;
  created_at?: string;
  updated_at?: string;
}

/**
 * 認証トークン情報
 */
export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in: number;
  user_id: string;
  email: string;
  full_name: string;
  picture?: string;
}

/**
 * ログインリクエスト
 */
export interface LoginRequest {
  email: string;
  password: string;
}

/**
 * ログインレスポンス
 */
export interface LoginResponse extends ApiResponse<AuthToken> {}

/**
 * トークンリフレッシュリクエスト
 */
export interface TokenRefreshRequest {
  token: string;
}

/**
 * トークンリフレッシュレスポンス
 */
export interface TokenRefreshResponse extends ApiResponse<AuthToken> {}

/**
 * ユーザー情報レスポンス
 */
export interface UserResponse extends ApiResponse<User> {}

/**
 * ユーザー設定
 */
export interface UserSettings {
  theme: 'light' | 'dark' | 'system';
  notifications_enabled: boolean;
  default_search_mode: 'hybrid' | 'semantic' | 'keyword';
  offline_mode_enabled: boolean;
}

/**
 * ユーザー設定レスポンス
 */
export interface UserSettingsResponse extends ApiResponse<UserSettings> {}

/**
 * ユーザー統計情報
 */
export interface UserStats {
  book_count: number;
  highlight_count: number;
  search_count: number;
  chat_count: number;
  last_activity: string;
}

/**
 * ユーザー統計情報レスポンス
 */
export interface UserStatsResponse extends ApiResponse<UserStats> {}
