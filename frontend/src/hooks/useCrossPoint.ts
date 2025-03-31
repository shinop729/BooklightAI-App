import { useState, useEffect, useCallback } from 'react';
import { getCrossPoint, likeCrossPoint, generateEmbeddings } from '../api/client';
import { CrossPoint, CrossPointResponse } from '../types';
import { useToast } from '../context/ToastContext';

/**
 * Cross Point関連のカスタムフック
 */
export const useCrossPoint = () => {
  const [crossPoint, setCrossPoint] = useState<CrossPoint | null>(null);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();

  /**
   * Cross Pointを取得する
   */
  const fetchCrossPoint = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await getCrossPoint();
      if (response.success && response.data) {
        setCrossPoint(response.data);
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        if (response.message) {
          showToast('warning', response.message);
        }
      }
    } catch (err) {
      console.error('Cross Point取得エラー:', err);
      setError('Cross Pointの取得中にエラーが発生しました');
      showToast('error', 'Cross Pointの取得中にエラーが発生しました');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  /**
   * Cross Pointをお気に入り登録/解除する
   */
  const toggleLike = useCallback(async (id: number) => {
    try {
      const response = await likeCrossPoint(id);
      if (response.success && response.data) {
        // 現在のCross Pointを更新
        setCrossPoint(prev => {
          if (prev && prev.id === id) {
            return {
              ...prev,
              liked: response.data!.liked
            };
          }
          return prev;
        });
        
        showToast(
          'success',
          response.data.liked 
            ? 'Cross Pointをお気に入りに登録しました' 
            : 'Cross Pointのお気に入りを解除しました'
        );
      }
    } catch (err) {
      console.error('Cross Pointお気に入り登録エラー:', err);
      showToast('error', 'お気に入り登録中にエラーが発生しました');
    }
  }, [showToast]);

  /**
   * 埋め込みベクトルを生成する（管理用）
   */
  const generateEmbeddingsForAll = useCallback(async () => {
    setLoading(true);
    try {
      const response = await generateEmbeddings();
      if (response.success) {
        showToast(
          'success',
          response.message || '埋め込みベクトルの生成が完了しました'
        );
        return response.data;
      } else {
        showToast(
          'error',
          response.message || '埋め込みベクトルの生成中にエラーが発生しました'
        );
      }
    } catch (err) {
      console.error('埋め込みベクトル生成エラー:', err);
      showToast('error', '埋め込みベクトルの生成中にエラーが発生しました');
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  // コンポーネントマウント時にCross Pointを取得
  useEffect(() => {
    fetchCrossPoint();
  }, [fetchCrossPoint]);

  return {
    crossPoint,
    loading,
    error,
    fetchCrossPoint,
    toggleLike,
    generateEmbeddingsForAll
  };
};
