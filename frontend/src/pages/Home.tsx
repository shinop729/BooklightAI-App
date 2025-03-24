import { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import HighlightCard from '../components/common/HighlightCard';

interface Highlight {
  content: string;
  title: string;
  author: string;
}

const Home = () => {
  const { user } = useAuth();
  const [randomHighlight, setRandomHighlight] = useState<Highlight | null>(null);
  const [loading, setLoading] = useState(true);

  // 仮のハイライトデータ（後でAPIから取得するように変更）
  const dummyHighlights: Highlight[] = [
    {
      content: "人生において重要なのは、どれだけ多くの呼吸をしたかではなく、どれだけ多くの瞬間に息をのんだかである。",
      title: "人生の意味を探して",
      author: "山田太郎"
    },
    {
      content: "最も困難な時期に示される勇気こそが、真の強さの証である。",
      title: "逆境からの学び",
      author: "佐藤次郎"
    },
    {
      content: "知識とは、事実を知ることではなく、行動することである。",
      title: "実践的知恵",
      author: "鈴木三郎"
    },
    {
      content: "本を読むことは、他人の頭で考えることである。自分で考えることだけが、自分自身を成長させる唯一の方法である。",
      title: "思考の技術",
      author: "高橋四郎"
    }
  ];

  // ランダムなハイライトを取得する関数
  const getRandomHighlight = () => {
    const randomIndex = Math.floor(Math.random() * dummyHighlights.length);
    return dummyHighlights[randomIndex];
  };

  // 新しいランダムハイライトを取得
  const refreshHighlight = () => {
    setLoading(true);
    // 実際のアプリでは、ここでAPIリクエストを行う
    setTimeout(() => {
      setRandomHighlight(getRandomHighlight());
      setLoading(false);
    }, 500); // 読み込み感を出すための遅延
  };

  // 初回レンダリング時にランダムハイライトを取得
  useEffect(() => {
    refreshHighlight();
  }, []);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-bold text-gray-100 mb-2">ようこそ、{user?.name || 'ゲスト'}さん</h1>
        <p className="text-gray-400">今日のランダムハイライト</p>
      </div>

      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
        {loading ? (
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
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <span className="text-gray-400">登録書籍数</span>
              <span className="text-white font-medium">12冊</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">ハイライト総数</span>
              <span className="text-white font-medium">247件</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">最近の検索</span>
              <span className="text-white font-medium">「人生」「学習」「成長」</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-gray-400">最終更新日</span>
              <span className="text-white font-medium">2025/03/20</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Home;
