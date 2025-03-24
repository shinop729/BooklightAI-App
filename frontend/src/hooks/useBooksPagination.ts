import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { Book, PaginatedBooksResponse } from '../types';

/**
 * ページネーション付き書籍一覧取得用のカスタムフック
 */
export const useBooksPagination = () => {
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(12);
  const [sortBy, setSortBy] = useState<'title' | 'author' | 'highlightCount'>('title');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');
  const [searchTerm, setSearchTerm] = useState('');
  
  // 書籍一覧の取得
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['books', page, pageSize, sortBy, sortOrder, searchTerm],
    queryFn: async () => {
      try {
        const params = new URLSearchParams({
          page: page.toString(),
          page_size: pageSize.toString(),
          sort_by: sortBy,
          sort_order: sortOrder,
          ...(searchTerm ? { search: searchTerm } : {})
        });
        
        console.log(`書籍一覧取得リクエスト: ${params.toString()}`);
        
        const { data } = await apiClient.get<PaginatedBooksResponse>(
          `/api/books?${params.toString()}`
        );
        
        // エラーレスポンスの場合
        if (!data.success) {
          throw new Error(data.error || 'データの取得に失敗しました');
        }
        
        return data.data;
      } catch (err) {
        console.error('書籍一覧取得エラー:', err);
        throw err;
      }
    },
    retry: 1 // エラー時に1回だけリトライ
  });
  
  // ページ変更
  const goToPage = (newPage: number) => {
    setPage(newPage);
  };
  
  // ページサイズ変更
  const changePageSize = (newSize: number) => {
    setPageSize(newSize);
    setPage(1); // ページサイズ変更時は1ページ目に戻る
  };
  
  // ソート変更
  const changeSort = (field: 'title' | 'author' | 'highlightCount') => {
    if (sortBy === field) {
      // 同じフィールドの場合は順序を反転
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      // 異なるフィールドの場合は昇順に設定
      setSortBy(field);
      setSortOrder('asc');
    }
  };
  
  // 検索語句変更
  const search = (term: string) => {
    setSearchTerm(term);
    setPage(1); // 検索時は1ページ目に戻る
  };
  
  return {
    books: data?.items || [],
    totalItems: data?.total || 0,
    totalPages: data?.total_pages || 0,
    currentPage: page,
    pageSize,
    isLoading,
    error,
    sortBy,
    sortOrder,
    searchTerm,
    goToPage,
    changePageSize,
    changeSort,
    search,
    refetch
  };
};
