import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { ApiResponse } from '../types';

/**
 * ランダムハイライト用の型定義
 */
export interface RandomHighlight {
  id: string;
  content: string;
  title: string;  // 書籍タイトル
  author: string; // 著者名
  bookId?: string;
  location?: string;
  createdAt?: string;
}

/**
 * ランダムハイライト取得用のレスポンス型
 */
interface RandomHighlightResponse extends ApiResponse<RandomHighlight> {}

/**
 * ランダムハイライト取得用のカスタムフック
 */
export const useRandomHighlight = () => {
  // リフェッチトリガー用の状態
  const [refreshIndex, setRefreshIndex] = useState(0);
  
  // ランダムハイライトの取得
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['randomHighlight', refreshIndex],
    queryFn: async (): Promise<RandomHighlight> => {
      const { data } = await apiClient.get<RandomHighlightResponse>('/highlights/random');
      return data.data;
    },
    // エラー時のリトライ回数
    retry: 1,
    // キャッシュ時間（5分）
    staleTime: 5 * 60 * 1000,
  });
  
  // 新しいランダムハイライトを取得
  const refreshHighlight = () => {
    setRefreshIndex(prev => prev + 1);
  };
  
  return {
    randomHighlight: data,
    isLoading,
    error,
    refreshHighlight
  };
};
