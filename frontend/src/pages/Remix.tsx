import { useState } from 'react';
import { useRemix } from '../hooks/useRemix';
import RemixCard from '../components/feature/RemixCard';
import { useAuth } from '../context/AuthContext';

/**
 * Remixページ
 */
const RemixPage = () => {
  const { user } = useAuth();
  const { remixes, currentRemix, loading, error, pagination, createRandomRemix, fetchUserRemixes } = useRemix();
  const [isGenerating, setIsGenerating] = useState(false);
  const [activeTab, setActiveTab] = useState<'create' | 'history'>('create');
  const [highlightCount, setHighlightCount] = useState<number>(5);

  // ランダムハイライトからRemix生成
  const handleRandomRemix = async () => {
    if (isGenerating) return;
    
    setIsGenerating(true);
    await createRandomRemix(highlightCount);
    setIsGenerating(false);
  };

  // タブ切り替え時にRemix履歴を取得
  const handleTabChange = (tab: 'create' | 'history') => {
    setActiveTab(tab);
    if (tab === 'history') {
      fetchUserRemixes();
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">Remix</h1>
        <p className="text-gray-400">ハイライトから新たな知恵を創造</p>
      </div>

      {/* タブ */}
      <div className="flex border-b border-gray-700 mb-6">
        <button
          className={`py-2 px-4 ${activeTab === 'create' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400'}`}
          onClick={() => handleTabChange('create')}
        >
          新規作成
        </button>
        <button
          className={`py-2 px-4 ${activeTab === 'history' ? 'text-blue-400 border-b-2 border-blue-400' : 'text-gray-400'}`}
          onClick={() => handleTabChange('history')}
        >
          履歴
        </button>
      </div>

      {/* 新規作成タブ */}
      {activeTab === 'create' && (
        <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
          <div className="mb-6 text-center">
            <h3 className="text-white text-lg mb-4">Remixを生成</h3>
            <p className="text-gray-400 mb-4">
              AIがランダムに選んだハイライトから、共通するテーマを見つけてエッセイを自動生成します。
              予想外の組み合わせから新たな発見が生まれます。
            </p>
            
            {/* ハイライト数選択 */}
            <div className="mb-4">
              <label className="text-gray-300 block mb-2">使用するハイライト数</label>
              <div className="flex justify-center space-x-2">
                {[3, 4, 5, 6, 7].map(count => (
                  <button
                    key={count}
                    onClick={() => setHighlightCount(count)}
                    className={`w-10 h-10 rounded-full ${
                      highlightCount === count
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                    }`}
                  >
                    {count}
                  </button>
                ))}
              </div>
              <p className="text-gray-400 text-sm mt-2">
                ハイライト数が多いほど多様な視点が含まれますが、テーマが散漫になる可能性があります
              </p>
            </div>
            
            <button
              onClick={handleRandomRemix}
              disabled={isGenerating}
              className="bg-blue-600 text-white px-6 py-3 rounded-lg text-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isGenerating ? '生成中...' : 'Remixを生成'}
            </button>
          </div>

          {loading ? (
            <div className="flex justify-center items-center h-60">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-4">{error}</p>
            </div>
          ) : currentRemix ? (
            <RemixCard remix={currentRemix} />
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-400 mb-4">
                「Remixを生成」ボタンをクリックすると、ハイライトを組み合わせた文章が生成されます。
              </p>
            </div>
          )}
        </div>
      )}

      {/* 履歴タブ */}
      {activeTab === 'history' && (
        <div>
          {loading ? (
            <div className="flex justify-center items-center h-60">
              <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : error ? (
            <div className="text-center py-8">
              <p className="text-red-400 mb-4">{error}</p>
              <button
                onClick={() => fetchUserRemixes()}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                再読み込み
              </button>
            </div>
          ) : remixes.length > 0 ? (
            <div className="space-y-6">
              {remixes.map(remix => (
                <RemixCard key={remix.id} remix={remix} isPreview={true} />
              ))}
              
              {/* ページネーション */}
              {pagination.totalPages > 1 && (
                <div className="flex justify-center mt-6">
                  <div className="flex space-x-2">
                    {Array.from({ length: pagination.totalPages }, (_, i) => i + 1).map(page => (
                      <button
                        key={page}
                        onClick={() => fetchUserRemixes(page, pagination.pageSize)}
                        className={`w-8 h-8 rounded ${
                          page === pagination.page
                            ? 'bg-blue-600 text-white'
                            : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                        }`}
                      >
                        {page}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ) : (
            <div className="text-center py-8">
              <p className="text-gray-400 mb-4">
                まだRemixがありません。「新規作成」タブでRemixを生成してみましょう。
              </p>
            </div>
          )}
        </div>
      )}

      {/* 説明セクション */}
      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mt-8">
        <h2 className="text-xl font-semibold text-white mb-4">Remixとは？</h2>
        <p className="text-gray-300 mb-4">
          Remixは、あなたのハイライトを組み合わせて新しい文章を生成する機能です。
          AIがランダムに選んだハイライトから共通するテーマを見つけ出し、一つの論理的な文章として再構成します。
        </p>
        <p className="text-gray-300 mb-4">
          Cross Point機能に近い発想で、予想外の組み合わせによって斬新な視点や発見をもたらします。
          異なる書籍からのハイライトが意外な形で繋がることで、新たな気づきが生まれます。
        </p>
        <p className="text-gray-300">
          これにより、あなたの読書体験から新たな知恵や洞察を引き出すことができます。
          AIが様々な書籍からハイライトを組み合わせ、創造的なエッセイを生成します。
        </p>
      </div>
    </div>
  );
};

export default RemixPage;
