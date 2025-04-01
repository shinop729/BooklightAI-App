import { useState, useCallback } from 'react';
import { useToast } from '../context/ToastContext';
import { Remix, RemixResponse, RemixListResponse, RandomThemeResponse } from '../types/remix';
import { generateRemix, getRemixById, getUserRemixes, getRandomTheme } from '../api/client';

/**
 * Remix機能のカスタムフック
 */
export const useRemix = () => {
  const [remixes, setRemixes] = useState<Remix[]>([]);
  const [currentRemix, setCurrentRemix] = useState<Remix | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [pagination, setPagination] = useState({
    page: 1,
    pageSize: 10,
    total: 0,
    totalPages: 0
  });
  const { showToast } = useToast();

  /**
   * ランダムテーマを取得する
   */
  const fetchRandomTheme = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getRandomTheme();
      if (response.success && response.data) {
        return response.data.theme;
      } else {
        showToast('warning', 'テーマの取得に失敗しました');
        return null;
      }
    } catch (err) {
      console.error('ランダムテーマ取得エラー:', err);
      showToast('error', 'テーマの取得中にエラーが発生しました');
      return null;
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  /**
   * ランダムハイライトからRemixを生成する
   */
  const createRandomRemix = useCallback(async (highlightCount: number = 5) => {
    setLoading(true);
    setError(null);
    try {
      const response = await generateRemix(highlightCount);
      if (response.success && response.data) {
        setCurrentRemix(response.data);
        showToast('success', 'Remixの生成が完了しました');
        return response.data;
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        showToast('warning', response.message || 'Remixの生成に失敗しました');
        return null;
      }
    } catch (err) {
      console.error('Remix生成エラー:', err);
      setError('Remixの生成中にエラーが発生しました');
      showToast('error', 'Remixの生成中にエラーが発生しました');
      return null;
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  /**
   * 指定したハイライト数でRemixを生成する
   */
  const createRemix = useCallback(async (highlightCount: number = 5) => {
    setLoading(true);
    setError(null);
    try {
      const response = await generateRemix(highlightCount);
      if (response.success && response.data) {
        setCurrentRemix(response.data);
        showToast('success', 'Remixの生成が完了しました');
        return response.data;
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        showToast('warning', response.message || 'Remixの生成に失敗しました');
        return null;
      }
    } catch (err) {
      console.error('Remix生成エラー:', err);
      setError('Remixの生成中にエラーが発生しました');
      showToast('error', 'Remixの生成中にエラーが発生しました');
      return null;
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  /**
   * IDでRemixを取得する
   */
  const fetchRemixById = useCallback(async (id: number) => {
    setLoading(true);
    setError(null);
    try {
      const response = await getRemixById(id);
      if (response.success && response.data) {
        setCurrentRemix(response.data);
        return response.data;
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        showToast('warning', response.message || 'Remixの取得に失敗しました');
        return null;
      }
    } catch (err) {
      console.error('Remix取得エラー:', err);
      setError('Remixの取得中にエラーが発生しました');
      showToast('error', 'Remixの取得中にエラーが発生しました');
      return null;
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  /**
   * ユーザーのRemix一覧を取得する
   */
  const fetchUserRemixes = useCallback(async (page: number = 1, pageSize: number = 10) => {
    setLoading(true);
    setError(null);
    try {
      const response = await getUserRemixes(page, pageSize);
      if (response.success && response.data) {
        setRemixes(response.data.items);
        setPagination({
          page: response.data.page,
          pageSize: response.data.page_size,
          total: response.data.total,
          totalPages: response.data.total_pages
        });
        return response.data.items;
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        showToast('warning', response.message || 'Remix一覧の取得に失敗しました');
        return [];
      }
    } catch (err) {
      console.error('Remix一覧取得エラー:', err);
      setError('Remix一覧の取得中にエラーが発生しました');
      showToast('error', 'Remix一覧の取得中にエラーが発生しました');
      return [];
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  return {
    remixes,
    currentRemix,
    loading,
    error,
    pagination,
    createRemix,
    fetchRemixById,
    fetchUserRemixes,
    fetchRandomTheme,
    createRandomRemix
  };
};
