import { useState, useEffect } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import { SearchHistoryItem, SearchHistoryResponse, ApiResponse } from '../types';

/**
 * 検索履歴管理用のカスタムフック
 */
export const useSearchHistory = () => {
  const queryClient = useQueryClient();
  
  // 検索履歴の取得
  const { data, isLoading, error } = useQuery({
    queryKey: ['searchHistory'],
    queryFn: async (): Promise<SearchHistoryItem[]> => {
      const { data } = await apiClient.get<SearchHistoryResponse>('/api/search/history');
      return data.data.history;
    },
    // キャッシュ時間（10分）
    staleTime: 10 * 60 * 1000,
  });
  
  // 検索履歴の追加
  const addToHistoryMutation = useMutation({
    mutationFn: async (keywords: string[]) => {
      await apiClient.post('/api/search/history', { keywords });
    },
    onSuccess: () => {
      // 成功時に検索履歴を再取得
      queryClient.invalidateQueries({ queryKey: ['searchHistory'] });
    }
  });
  
  // 検索履歴の削除
  const deleteFromHistoryMutation = useMutation({
    mutationFn: async (historyId: string) => {
      await apiClient.delete(`/api/search/history/${historyId}`);
    },
    onSuccess: () => {
      // 成功時に検索履歴を再取得
      queryClient.invalidateQueries({ queryKey: ['searchHistory'] });
    }
  });
  
  // 検索履歴のクリア
  const clearHistoryMutation = useMutation({
    mutationFn: async () => {
      await apiClient.delete('/api/search/history');
    },
    onSuccess: () => {
      // 成功時に検索履歴を再取得
      queryClient.invalidateQueries({ queryKey: ['searchHistory'] });
    }
  });
  
  // 検索履歴に追加
  const addToHistory = (keywords: string[]) => {
    if (keywords.length > 0) {
      addToHistoryMutation.mutate(keywords);
    }
  };
  
  // 検索履歴から削除
  const deleteFromHistory = (historyId: string) => {
    deleteFromHistoryMutation.mutate(historyId);
  };
  
  // 検索履歴をクリア
  const clearHistory = () => {
    clearHistoryMutation.mutate();
  };
  
  return {
    history: data || [],
    isLoading,
    error,
    addToHistory,
    deleteFromHistory,
    clearHistory,
    isAdding: addToHistoryMutation.isPending,
    isDeleting: deleteFromHistoryMutation.isPending,
    isClearing: clearHistoryMutation.isPending
  };
};
