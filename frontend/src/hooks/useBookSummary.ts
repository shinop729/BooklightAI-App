import { useState } from 'react';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import apiClient from '../api/client';
import { GenerateSummaryRequest, GenerateSummaryResponse, Book } from '../types';
import { useSummaryProgressStore } from '../store/summaryProgressStore';

/**
 * 書籍サマリー生成用のカスタムフック
 */
export const useBookSummary = () => {
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  
  // サマリー進捗状態管理
  const { 
    startProgress, 
    setCurrentBook, 
    incrementProgress, 
    completeProgress, 
    setError: setProgressError 
  } = useSummaryProgressStore();
  
  // サマリー生成ミューテーション
  const { mutate, isPending } = useMutation({
    mutationFn: async (bookId: string) => {
      const request: GenerateSummaryRequest = { bookId };
      const { data } = await apiClient.post<GenerateSummaryResponse>(
        '/api/books/generate-summary',
        request
      );
      return data.data.summary;
    },
    onMutate: (bookId) => {
      // 書籍情報の取得
      const book = queryClient.getQueryData<Book>(['book', bookId]);
      if (book) {
        // 進捗状態の初期化
        startProgress(1);
        setCurrentBook(book.title);
      }
      setError(null);
    },
    onSuccess: (summary, bookId) => {
      // 進捗状態の更新
      incrementProgress();
      completeProgress();
      
      // 書籍データのキャッシュを更新
      queryClient.invalidateQueries({ queryKey: ['book', bookId] });
      queryClient.invalidateQueries({ queryKey: ['books'] });
    },
    onError: (err) => {
      setProgressError();
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('サマリー生成中にエラーが発生しました');
      }
    }
  });
  
  // サマリー生成関数
  const generateSummary = (bookId: string) => {
    if (!bookId) {
      setError('書籍IDが指定されていません');
      return;
    }
    
    mutate(bookId);
  };
  
  return {
    generateSummary,
    isGenerating: isPending,
    error
  };
};
