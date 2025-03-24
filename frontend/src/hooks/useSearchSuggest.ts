import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { SearchSuggestResponse } from '../types';
import { useDebounce } from './useDebounce';

/**
 * 検索サジェスト用のカスタムフック
 * 入力値に基づいて検索キーワードの候補を取得する
 */
export const useSearchSuggest = (inputValue: string) => {
  // 入力値のデバウンス処理（300ms）
  const debouncedInput = useDebounce(inputValue, 300);
  
  // サジェスト候補の取得
  const { data, isLoading, error } = useQuery({
    queryKey: ['searchSuggest', debouncedInput],
    queryFn: async (): Promise<string[]> => {
      if (!debouncedInput || debouncedInput.length < 2) {
        return [];
      }
      
      const { data } = await apiClient.get<SearchSuggestResponse>(
        `/api/v2/search/suggest?q=${encodeURIComponent(debouncedInput)}`
      );
      
      return data.data.suggestions;
    },
    // 入力が2文字未満の場合は実行しない
    enabled: debouncedInput.length >= 2,
    // キャッシュ時間（5分）
    staleTime: 5 * 60 * 1000,
  });
  
  return {
    suggestions: data || [],
    isLoading,
    error
  };
};
