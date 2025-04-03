import { useState, useCallback, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient, { searchHighlights, prefetchSearchResults, clearSearchCache } from '../api/client';
import { SearchResult, SearchRequest, SearchResponse } from '../types';
import { useDebounce } from './useDebounce';

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
  const [isSearching, setIsSearching] = useState(false);
  
  // キーワードの変更をデバウンス
  const debouncedKeywords = useDebounce(keywords, 300);
  
  // React Query を使用したAPI通信（シンプル化）
  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ['search', debouncedKeywords],
    queryFn: async () => {
      if (debouncedKeywords.length === 0) return { results: [] };
      
      setIsSearching(true);
      
      try {
        console.log('検索リクエスト送信:', { keywords: debouncedKeywords });
        
        const searchRequest: SearchRequest = {
          keywords: debouncedKeywords,
          limit: 30
        };
        
        // 検索関数を使用
        const response = await searchHighlights(searchRequest);
        console.log('検索レスポンス受信:', response);
        
        if (!response.success) {
          throw new Error(response.message || '検索に失敗しました');
        }
        
        return response.data;
      } catch (err) {
        console.error('検索エラー:', err);
        throw err;
      } finally {
        setIsSearching(false);
      }
    },
    // キーワードが空の場合は実行しない
    enabled: debouncedKeywords.length > 0,
    // キャッシュ設定
    staleTime: 5 * 60 * 1000,  // 5分間キャッシュ
    gcTime: 10 * 60 * 1000  // 10分間キャッシュを保持
  });
  
  // キーワード変更時に自動的に検索を実行
  useEffect(() => {
    if (debouncedKeywords.length > 0) {
      refetch();
    }
  }, [debouncedKeywords, refetch]);
  
  const addKeyword = useCallback((keyword: string) => {
    if (keyword && !keywords.includes(keyword)) {
      setKeywords(prev => [...prev, keyword]);
    }
  }, [keywords]);
  
  const removeKeyword = useCallback((keyword: string) => {
    setKeywords(prev => prev.filter(k => k !== keyword));
  }, []);
  
  const clearKeywords = useCallback(() => {
    setKeywords([]);
  }, []);
  
  /**
   * 検索オプションを設定（シンプル化のため現在は使用しない）
   */
  const setSearchOptions = useCallback((_newOptions: SearchOptions) => {
    // シンプル化のため、オプション設定は無効化
    console.log('検索オプションの設定は現在無効化されています');
  }, []);
  
  /**
   * 検索キャッシュをクリア
   */
  const clearCache = useCallback(() => {
    clearSearchCache();
  }, []);
  
  return {
    keywords,
    results: data?.results || ([] as any[]),
    isLoading: isLoading || isRefetching || isSearching,
    error,
    addKeyword,
    removeKeyword,
    clearKeywords,
    search: refetch,
    setSearchOptions,
    clearCache
  };
};
