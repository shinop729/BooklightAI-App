import { useState, useEffect, useCallback, useRef } from 'react';
import { getCrossPoint, likeCrossPoint, generateEmbeddings } from '../api/client';
import { CrossPoint, CrossPointResponse } from '../types';
import { useToast } from '../context/ToastContext';
import { debounce } from '../utils/textUtils';

// グローバルキャッシュ
let globalCrossPointData: CrossPoint | null = null;
// フェッチフラグをグローバルに管理
let hasFetchedCrossPoint = false;
// 最後のフェッチ時間を記録
let lastFetchTime = 0;
// フェッチの最小間隔（ミリ秒）
const FETCH_INTERVAL = 60000; // 1分

/**
 * Cross Point関連のカスタムフック
 */
export const useCrossPoint = () => {
  const [crossPoint, setCrossPoint] = useState<CrossPoint | null>(globalCrossPointData);
  const [loading, setLoading] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const { showToast } = useToast();
  const isMounted = useRef(true);

  // コンポーネントのマウント状態を管理
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  /**
   * Cross Pointを取得する
   */
  const fetchCrossPoint = useCallback(async () => {
    // グローバルキャッシュがある場合はそれを使用
    if (globalCrossPointData) {
      console.log('グローバルキャッシュからCross Pointを使用');
      setCrossPoint(globalCrossPointData);
      return;
    }
    
    // 前回のフェッチから最小間隔が経過していない場合はスキップ
    const now = Date.now();
    if (now - lastFetchTime < FETCH_INTERVAL) {
      console.log('Cross Pointフェッチをスキップ: 最小間隔内の再フェッチ');
      return;
    }
    
    // フェッチ時間を更新
    lastFetchTime = now;
    
    // 既にフェッチ済みの場合はスキップ
    if (hasFetchedCrossPoint) {
      console.log('Cross Pointは既にフェッチ済みです');
      return;
    }
    
    console.log('Cross Pointをサーバーから取得します');
    setLoading(true);
    setError(null);
    
    try {
      hasFetchedCrossPoint = true; // フェッチ開始前にフラグを設定
      
      const response = await getCrossPoint();
      
      // コンポーネントがアンマウントされていたら処理を中止
      if (!isMounted.current) return;
      
      if (response.success && response.data) {
        globalCrossPointData = response.data; // グローバルキャッシュを更新
        setCrossPoint(response.data);
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        if (response.message) {
          showToast('warning', response.message);
        }
      }
    } catch (err) {
      // コンポーネントがアンマウントされていたら処理を中止
      if (!isMounted.current) return;
      
      console.error('Cross Point取得エラー:', err);
      setError('Cross Pointの取得中にエラーが発生しました');
      showToast('error', 'Cross Pointの取得中にエラーが発生しました');
      
      // エラー時はフラグをリセット（再試行可能に）
      hasFetchedCrossPoint = false;
    } finally {
      // コンポーネントがアンマウントされていたら処理を中止
      if (!isMounted.current) return;
      
      setLoading(false);
    }
  }, []); // 依存配列を空に

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

  // コンポーネントマウント時に一度だけCross Pointを取得
  useEffect(() => {
    // すでにデータがある場合はスキップ
    if (crossPoint) {
      console.log('既存のCross Pointデータがあります');
      return;
    }
    
    console.log('Cross Pointフェッチを開始します');
    fetchCrossPoint();
    
    // コンポーネントのアンマウント時の処理
    return () => {
      console.log('Cross Pointコンポーネントがアンマウントされました');
    };
  }, [fetchCrossPoint]);

  return {
    crossPoint,
    loading,
    error,
    fetchCrossPoint,
    toggleLike,
    generateEmbeddingsForAll
  };

  /**
   * Cross Pointを強制的に再取得する関数
   * キャッシュやフラグを無視してAPIを呼び出す
   */
  const forceFetchCrossPoint = useCallback(async () => {
    console.log('Cross Pointを強制的に再取得します');
    setLoading(true);
    setError(null);

    // 前回のフェッチからの間隔をチェック（短時間の連続クリック防止）
    const now = Date.now();
    if (now - lastFetchTime < 1000) { // 1秒未満のクリックは無視
      console.log('短すぎる間隔での再フェッチ試行を無視');
      setLoading(false); // ローディング状態を解除
      return;
    }
    lastFetchTime = now; // フェッチ時間を更新

    try {
      const response = await getCrossPoint();

      if (!isMounted.current) return;

      if (response.success && response.data) {
        globalCrossPointData = response.data; // グローバルキャッシュを更新
        setCrossPoint(response.data);
        hasFetchedCrossPoint = true; // フェッチ成功フラグを立てる
        showToast('success', '新しいCross Pointを取得しました');
      } else {
        setError(response.message || '予期せぬエラーが発生しました');
        if (response.message) {
          showToast('warning', response.message);
        }
        // エラー時はフラグをリセットしない（再試行はボタンクリックで行う）
      }
    } catch (err) {
      if (!isMounted.current) return;

      console.error('Cross Point強制取得エラー:', err);
      setError('Cross Pointの取得中にエラーが発生しました');
      showToast('error', 'Cross Pointの取得中にエラーが発生しました');
      // エラー時はフラグをリセットしない
    } finally {
      if (!isMounted.current) return;
      setLoading(false);
    }
  }, [showToast]); // showToastのみ依存

  // コンポーネントマウント時に一度だけCross Pointを取得
  useEffect(() => {
    // すでにデータがある場合はスキップ
    if (crossPoint) {
      console.log('既存のCross Pointデータがあります');
      return;
    }

    console.log('Cross Pointフェッチを開始します');
    fetchCrossPoint();

    // コンポーネントのアンマウント時の処理
    return () => {
      console.log('Cross Pointコンポーネントがアンマウントされました');
    };
  }, [fetchCrossPoint]); // fetchCrossPointに依存

  return {
    crossPoint,
    loading,
    error,
    fetchCrossPoint, // 既存の関数も残す
    toggleLike,
    generateEmbeddingsForAll,
    forceFetchCrossPoint // 新しい関数を戻り値に追加
  };
};
