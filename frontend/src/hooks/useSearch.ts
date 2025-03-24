import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { SearchResult, SearchRequest, SearchResponse } from '../types';

export const useSearch = (initialKeywords: string[] = []) => {
  const [keywords, setKeywords] = useState<string[]>(initialKeywords);
  
  // TanStack Query を使用したAPI通信
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['search', keywords],
    queryFn: async () => {
      if (keywords.length === 0) return { results: [] };
      
      const searchRequest: SearchRequest = {
        keywords,
        hybrid_alpha: 0.7,
        book_weight: 0.3,
        use_expanded: true
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
  
  return {
    keywords,
    results: data?.results || [],
    isLoading,
    error,
    addKeyword,
    removeKeyword,
    clearKeywords,
    search: refetch
  };
};
