import { useState } from 'react';
import { useCrossPoint } from '../hooks/useCrossPoint';
import CrossPointCard from '../components/feature/CrossPointCard';
import { useAuth } from '../context/AuthContext';

/**
 * Cross Pointページ
 */
const CrossPointPage = () => {
  const { user } = useAuth();
  const { crossPoint, loading, error, fetchCrossPoint, toggleLike, generateEmbeddingsForAll } = useCrossPoint();
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationResult, setGenerationResult] = useState<{
    processed: number;
    total: number;
  } | null>(null);

  // 埋め込みベクトル生成（管理者用）
  const handleGenerateEmbeddings = async () => {
    if (isGenerating) return;
    
    setIsGenerating(true);
    setGenerationResult(null);
    
    try {
      const result = await generateEmbeddingsForAll();
      if (result) {
        setGenerationResult({
          processed: result.processed_count,
          total: result.total_count
        });
      }
    } catch (err) {
      console.error('埋め込みベクトル生成エラー:', err);
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">Cross Point</h1>
        <p className="text-gray-400">異なる書籍間の意外な繋がりを発見</p>
      </div>

      {/* メインコンテンツ */}
      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
        {loading ? (
          <div className="flex justify-center items-center h-60">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <p className="text-red-400 mb-4">{error}</p>
            <button
              onClick={fetchCrossPoint}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
            >
              再読み込み
            </button>
          </div>
        ) : crossPoint ? (
          <div>
            <CrossPointCard
              crossPoint={crossPoint}
              onLike={toggleLike}
              loading={loading}
            />
            <div className="mt-6 text-center">
              <button
                onClick={fetchCrossPoint}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
                disabled={loading}
              >
                新しいCross Pointを生成
              </button>
            </div>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-gray-400 mb-4">Cross Pointを生成するには、少なくとも2冊の書籍からのハイライトが必要です。</p>
            <a href="/upload" className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors inline-block">
              ハイライトをアップロードする
            </a>
          </div>
        )}
      </div>

      {/* 説明セクション */}
      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">Cross Pointとは？</h2>
        <p className="text-gray-300 mb-4">
          Cross Pointは、あなたが読んだ異なる書籍間の意外な繋がりを発見する機能です。
          一見関連性のない2つの書籍のハイライトを、AIが深層的な視点で結びつけます。
        </p>
        <p className="text-gray-300">
          これにより、新たな視点や洞察を得ることができ、読書体験がより豊かになります。
          毎日新しいCross Pointが生成され、あなたの知識の世界を広げます。
        </p>
      </div>

      {/* 管理者用セクション */}
      {user && user.email === 'admin@example.com' && (
        <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-xl font-semibold text-white mb-4">管理者機能</h2>
          <div className="space-y-4">
            <div>
              <button
                onClick={handleGenerateEmbeddings}
                disabled={isGenerating}
                className="px-4 py-2 bg-purple-600 text-white rounded hover:bg-purple-700 transition-colors disabled:opacity-50"
              >
                {isGenerating ? '生成中...' : '全ハイライトの埋め込みベクトルを生成'}
              </button>
              
              {generationResult && (
                <div className="mt-2 text-gray-300">
                  <p>処理完了: {generationResult.processed} / {generationResult.total} ハイライト</p>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CrossPointPage;
