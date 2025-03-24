import { useAuth } from '../context/AuthContext';
import { useRandomHighlight } from '../hooks/useRandomHighlight';
import { useUserStats } from '../hooks/useUserStats';
import HighlightCard from '../components/common/HighlightCard';
import { formatDate } from '../utils/textUtils';

const Home = () => {
  const { user } = useAuth();
  const { randomHighlight, isLoading: highlightLoading, refreshHighlight } = useRandomHighlight();
  const { stats, isLoading: statsLoading } = useUserStats();

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">ようこそ、{user?.name || 'ゲスト'}さん</h1>
        <p className="text-gray-400">今日のランダムハイライト</p>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
        {highlightLoading ? (
          <div className="flex justify-center items-center h-40">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : randomHighlight ? (
          <div>
            <HighlightCard
              content={randomHighlight.content}
              title={randomHighlight.title}
              author={randomHighlight.author}
            />
            <div className="mt-4 text-center">
              <button
                onClick={refreshHighlight}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
              >
                別のハイライトを表示
              </button>
            </div>
          </div>
        ) : (
          <p className="text-gray-400 text-center">ハイライトが見つかりませんでした。</p>
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-xl font-semibold text-white mb-4">クイックアクセス</h2>
          <div className="grid grid-cols-2 gap-4">
            <a href="/search" className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg text-center transition-colors">
              <div className="text-3xl mb-2">🔍</div>
              <div className="text-white">検索</div>
            </a>
            <a href="/chat" className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg text-center transition-colors">
              <div className="text-3xl mb-2">💬</div>
              <div className="text-white">チャット</div>
            </a>
            <a href="/books" className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg text-center transition-colors">
              <div className="text-3xl mb-2">📚</div>
              <div className="text-white">書籍一覧</div>
            </a>
            <a href="/upload" className="bg-gray-700 hover:bg-gray-600 p-4 rounded-lg text-center transition-colors">
              <div className="text-3xl mb-2">📤</div>
              <div className="text-white">アップロード</div>
            </a>
          </div>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-xl font-semibold text-white mb-4">統計情報</h2>
          {statsLoading ? (
            <div className="flex justify-center items-center h-40">
              <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500"></div>
            </div>
          ) : stats ? (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <span className="text-gray-400">登録書籍数</span>
                <span className="text-white font-medium">{stats.book_count}冊</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">ハイライト総数</span>
                <span className="text-white font-medium">{stats.highlight_count}件</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">検索回数</span>
                <span className="text-white font-medium">{stats.search_count}回</span>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-gray-400">最終アクティビティ</span>
                <span className="text-white font-medium">{formatDate(stats.last_activity)}</span>
              </div>
            </div>
          ) : (
            <p className="text-gray-400 text-center">統計情報を読み込めませんでした</p>
          )}
        </div>
      </div>
    </div>
  );
};

export default Home;
