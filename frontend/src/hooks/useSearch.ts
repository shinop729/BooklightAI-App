import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { SearchResult, SearchRequest, SearchResponse } from '../types';

/**
 * 検索オプション
 */
interface SearchOptions {
  hybrid_alpha?: number; // ベクトル検索の重み（0-1）
  book_weight?: number; // 書籍情報の重み（0-1）
  use_expanded?: boolean; // 拡張検索の使用
  limit?: number; // 結果の最大数
}

export const useSearch = (initialKeywords: string[] = []) => {
  const [keywords, setKeywords] = useState<string[]>(initialKeywords);
  const [options, setOptions] = useState<SearchOptions>({
    hybrid_alpha: 0.7,
    book_weight: 0.3,
    use_expanded: true
  });
  
  // TanStack Query を使用したAPI通信
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['search', keywords, options],
    queryFn: async () => {
      if (keywords.length === 0) return { results: [] };
      
      const searchRequest: SearchRequest = {
        keywords,
        ...options
      };
      
      const { data } = await apiClient.post<SearchResponse>('/api/v2/search', searchRequest);
      
      return data.data;
    },
    // キーワードが空の場合は実行しない
    enabled: keywords.length > 0
  });
  
  const addKeyword = (keyword: string) => {
    if (keyword && !keywords.includes(keyword)) {
      setKeywords([...keywords, keyword]);
    }
  };
  
  const removeKeyword = (keyword: string) => {
    setKeywords(keywords.filter(k => k !== keyword));
  };
  
  const clearKeywords = () => {
    setKeywords([]);
  };
  
  /**
   * 検索オプションを設定
   */
  const setSearchOptions = (newOptions: SearchOptions) => {
    setOptions(prev => ({ ...prev, ...newOptions }));
  };
  
  return {
    keywords,
    results: data?.results || [],
    isLoading,
    error,
    addKeyword,
    removeKeyword,
    clearKeywords,
    search: refetch,
    setSearchOptions
  };
};
