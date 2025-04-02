import { createContext, useContext, ReactNode, useRef, useEffect, useState } from 'react'; // useState を追加
import { useQuery, useQueryClient } from '@tanstack/react-query';
// getCrossPointForce をインポート
import { getCrossPoint, getCrossPointForce, likeCrossPoint, generateEmbeddings } from '../api/client';
import { CrossPoint, CrossPointResponse } from '../types'; // CrossPointResponse をインポート
import { useToast } from './ToastContext';

// クエリキー（固定値として使用）
const CROSS_POINT_QUERY_KEY = ['crossPoint', 'fixed'];

// コンテキストの型定義
interface CrossPointContextType {
  crossPoint: CrossPoint | null;
  loading: boolean;
  error: string | null;
  fetchCrossPoint: () => Promise<void>; // 既存の関数
  forceFetchCrossPoint: () => Promise<void>; // 新しい関数を追加
  toggleLike: (id: number) => Promise<void>;
  generateEmbeddingsForAll: () => Promise<any>;
}

// コンテキストの作成
const CrossPointContext = createContext<CrossPointContextType | undefined>(undefined);

// プロバイダーコンポーネント
export const CrossPointProvider = ({ children }: { children: ReactNode }) => {
  const { showToast } = useToast();
  const queryClient = useQueryClient();
  const isMounted = useRef(true);
  // ローディング状態を別途管理（useQueryのisLoadingとは別に）
  const [isForceFetching, setIsForceFetching] = useState(false);

  // コンポーネントのマウント状態を管理
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  // React Queryを使用してCross Pointデータを取得（設定を最適化）
  const {
    data: crossPoint,
    isLoading: initialLoading, // 初回ロード用のisLoading
    error,
    refetch // fetchCrossPoint (通常) で使用
  } = useQuery<CrossPoint, Error>({
    queryKey: CROSS_POINT_QUERY_KEY,
    queryFn: async () => {
      // コンポーネントがアンマウントされていたら処理を中止
      if (!isMounted.current) return null as any;
      
      console.log('Cross Pointデータを取得中...');
      const response = await getCrossPoint();
      
      // コンポーネントがアンマウントされていたら処理を中止
      if (!isMounted.current) return null as any;
      
      if (response.success && response.data) {
        return response.data;
      }
      throw new Error(response.message || '予期せぬエラーが発生しました');
    },
    // 重要な設定：自動再取得を無効化
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
    staleTime: Infinity, // データを常に新鮮として扱う
    gcTime: Infinity, // キャッシュを永続化（cacheTimeの代わりにgcTimeを使用）
    retry: false, // リトライしない
    enabled: true, // 初回のみ実行
    refetchInterval: false, // 定期的な再取得を無効化
    refetchIntervalInBackground: false // バックグラウンドでの再取得も無効化
  });

  // エラーハンドリング
  if (error) {
    console.error('Cross Point取得エラー:', error);
    showToast('error', error.message || 'Cross Pointの取得中にエラーが発生しました');
  }

  // 手動でデータを再取得する関数
  const fetchCrossPoint = async () => {
    try {
      await refetch();
    } catch (err) {
      console.error('Cross Point再取得エラー:', err);
    }
  };

  // 強制的にデータを再取得する関数 (getCrossPointForce を使用)
  const forceFetchCrossPoint = async () => {
    console.log('Cross Pointを強制的に再取得します (API直接呼び出し)');
    setIsForceFetching(true); // ローディング開始
    try {
      // localStorageキャッシュを無視するAPI関数を呼び出す
      const response: CrossPointResponse = await getCrossPointForce();

      if (!isMounted.current) return; // アンマウントチェック

      if (response.success && response.data) {
        // React Queryのキャッシュを手動で更新
        queryClient.setQueryData(CROSS_POINT_QUERY_KEY, response.data);
        showToast('success', '新しいCross Pointを取得しました');
      } else {
        // APIからのエラーメッセージを表示
        showToast('error', response.message || 'Cross Pointの取得に失敗しました');
      }
    } catch (err) {
      if (!isMounted.current) return; // アンマウントチェック
      console.error('Cross Point強制再取得エラー:', err);
      showToast('error', 'Cross Pointの再取得中にエラーが発生しました');
    } finally {
      // アンマウントチェック後にローディング状態を解除
      if (isMounted.current) {
        setIsForceFetching(false);
      }
    }
  };

  // お気に入り登録/解除
  const toggleLike = async (id: number) => {
    try {
      const response = await likeCrossPoint(id);
      if (response.success && response.data) {
        // キャッシュを更新
        queryClient.setQueryData([CROSS_POINT_QUERY_KEY], (oldData: CrossPoint | undefined) => {
          if (oldData && oldData.id === id) {
            return {
              ...oldData,
              liked: response.data!.liked
            };
          }
          return oldData;
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
  };

  // 埋め込みベクトル生成（管理用）
  const generateEmbeddingsForAll = async () => {
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
    }
  };

  // コンテキスト値
  const value: CrossPointContextType = {
    crossPoint: crossPoint || null,
    // ローディング状態は初回ロードと強制フェッチを組み合わせる
    loading: initialLoading || isForceFetching,
    error: error ? error.message : null,
    fetchCrossPoint,
    forceFetchCrossPoint,
    toggleLike,
    generateEmbeddingsForAll
  };

  return (
    <CrossPointContext.Provider value={value}>
      {children}
    </CrossPointContext.Provider>
  );
};

// カスタムフック
export const useCrossPoint = () => {
  const context = useContext(CrossPointContext);
  if (context === undefined) {
    throw new Error('useCrossPoint must be used within a CrossPointProvider');
  }
  return context;
};
