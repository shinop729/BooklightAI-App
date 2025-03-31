import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import apiClient from '../api/client';
import { Book, PaginatedBooksResponse } from '../types';

interface PaginatedBooks {
  items: Book[];
  total: number;
  total_pages: number;
  page: number;
  page_size: number;
}

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
  const { data, isLoading, error, refetch } = useQuery<PaginatedBooks, Error>({
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
        
        console.log(`書籍一覧取得リクエスト詳細:`, {
          url: `/api/books?${params.toString()}`,
          page,
          pageSize,
          sortBy,
          sortOrder,
          searchTerm
        });
        
        const { data } = await apiClient.get<PaginatedBooksResponse>(
          `/api/books?${params.toString()}`
        );
        
        // エラーレスポンスの場合
        if (!data.success) {
          throw new Error(data.error || 'データの取得に失敗しました');
        }
        
        console.log(`APIレスポンス詳細:`, {
          totalItems: data.data.total,
          totalPages: data.data.total_pages,
          currentPage: data.data.page,
          itemsCount: data.data.items.length
        });
        
        return data.data;
      } catch (err) {
        console.error('書籍一覧取得エラー:', err);
        throw err;
      }
    },
    retry: 1, // エラー時に1回だけリトライ
    staleTime: 0, // データをすぐに古いとみなす
    refetchOnWindowFocus: false // ウィンドウフォーカス時の再取得を無効化
  });
  
  // ページ変更
  const goToPage = (newPage: number) => {
    console.log(`ページを変更: ${page} -> ${newPage}`);
    // 現在のページと同じ場合は何もしない
    if (newPage === page) {
      console.log(`現在のページと同じため、何もしません`);
      return;
    }
    
    // ページを変更
    setPage(newPage);
    
    // 明示的なデータの再取得
    // クロージャを使用して、newPageの値を保持する
    const targetPage = newPage;
    
    // 直接queryKeyを更新して、正しいページのデータを取得する
    const fetchPageData = async () => {
      try {
        console.log(`ページ${targetPage}のデータを再取得（遅延実行）`);
        
        const params = new URLSearchParams({
          page: targetPage.toString(),
          page_size: pageSize.toString(),
          sort_by: sortBy,
          sort_order: sortOrder,
          ...(searchTerm ? { search: searchTerm } : {})
        });
        
        console.log(`明示的なAPIリクエスト:`, {
          url: `/api/books?${params.toString()}`,
          page: targetPage,
          pageSize,
          sortBy,
          sortOrder,
          searchTerm
        });
        
        const { data } = await apiClient.get<PaginatedBooksResponse>(
          `/api/books?${params.toString()}`
        );
        
        if (!data.success) {
          throw new Error(data.error || 'データの取得に失敗しました');
        }
        
        console.log(`ページ${targetPage}のデータ取得成功:`, {
          totalItems: data.data.total,
          totalPages: data.data.total_pages,
          currentPage: data.data.page,
          itemsCount: data.data.items.length
        });
        
        // 取得したデータを直接設定
        return data.data;
      } catch (err) {
        console.error(`ページ${targetPage}のデータ取得エラー:`, err);
        throw err;
      }
    };
    
    // 時間をさらに長めに設定して、他の処理が完了した後に実行されるようにする
    setTimeout(() => {
      fetchPageData()
        .then(() => console.log(`ページ${targetPage}のデータ取得完了`))
        .catch(err => console.error(`ページ${targetPage}のデータ取得失敗:`, err));
    }, 300);
  };
  
  // ページサイズ変更
  const changePageSize = (newSize: number) => {
    console.log(`ページサイズを変更: ${pageSize} -> ${newSize}`);
    setPageSize(newSize);
    setPage(1); // ページサイズ変更時は1ページ目に戻る
    // 明示的なデータの再取得
    console.log('ページサイズ変更によるデータ再取得を実行');
    refetch();
  };
  
  // ソート変更
  const changeSort = (field: 'title' | 'author' | 'highlightCount') => {
    console.log(`ソート変更: ${sortBy}(${sortOrder}) -> ${field}`);
    if (sortBy === field) {
      // 同じフィールドの場合は順序を反転
      const newOrder = sortOrder === 'asc' ? 'desc' : 'asc';
      console.log(`ソート順を反転: ${sortOrder} -> ${newOrder}`);
      setSortOrder(newOrder);
    } else {
      // 異なるフィールドの場合は昇順に設定
      console.log(`ソートフィールドを変更: ${sortBy} -> ${field}`);
      setSortBy(field);
      setSortOrder('asc');
    }
    // 明示的なデータの再取得
    console.log('ソート変更によるデータ再取得を実行');
    refetch();
  };
  
  // 検索語句変更
  const search = (term: string) => {
    console.log(`検索語句を変更: "${searchTerm}" -> "${term}"`);
    // 検索語句が変更された場合のみページをリセット
    if (term !== searchTerm) {
      setSearchTerm(term);
      setPage(1); // 検索時は1ページ目に戻る
      // 明示的なデータの再取得
      console.log('検索語句変更によるデータ再取得を実行');
      refetch();
    }
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
