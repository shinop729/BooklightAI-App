import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { UserStats, UserStatsResponse } from '../types';

/**
 * ユーザー統計情報取得用のカスタムフック
 */
export const useUserStats = () => {
  // ユーザー統計情報の取得
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['userStats'],
    queryFn: async (): Promise<UserStats> => {
      const { data } = await apiClient.get<UserStatsResponse>('/user/stats');
      return data.data;
    },
    // エラー時のリトライ回数
    retry: 1,
    // キャッシュ時間（10分）
    staleTime: 10 * 60 * 1000,
    // 最近の検索キーワードなどの情報を含むため、
    // ページ遷移時に再取得する
    refetchOnWindowFocus: true,
  });
  
  return {
    stats: data,
    isLoading,
    error,
    refetch
  };
};
