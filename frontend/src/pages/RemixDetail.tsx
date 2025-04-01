import { useEffect } from 'react';
import { useParams, Link, useNavigate } from 'react-router-dom';
import { useRemix } from '../hooks/useRemix';
import RemixCard from '../components/feature/RemixCard';

/**
 * Remix詳細ページ
 */
const RemixDetailPage = () => {
  const { id } = useParams<{ id: string }>();
  const { currentRemix, loading, error, fetchRemixById } = useRemix();
  const navigate = useNavigate();

  useEffect(() => {
    if (id) {
      const remixId = parseInt(id);
      if (!isNaN(remixId)) {
        fetchRemixById(remixId);
      }
    }
  }, [id, fetchRemixById]);

  // 戻るボタンのハンドラ
  const handleBack = () => {
    navigate('/remix');
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-6">
        <button
          onClick={handleBack}
          className="flex items-center text-blue-400 hover:text-blue-300"
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className="h-5 w-5 mr-1"
            viewBox="0 0 20 20"
            fill="currentColor"
          >
            <path
              fillRule="evenodd"
              d="M9.707 16.707a1 1 0 01-1.414 0l-6-6a1 1 0 010-1.414l6-6a1 1 0 011.414 1.414L5.414 9H17a1 1 0 110 2H5.414l4.293 4.293a1 1 0 010 1.414z"
              clipRule="evenodd"
            />
          </svg>
          Remix一覧に戻る
        </button>
      </div>

      {loading ? (
        <div className="flex justify-center items-center h-60">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="text-center py-8">
          <p className="text-red-400 mb-4">{error}</p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Remix一覧に戻る
          </button>
        </div>
      ) : currentRemix ? (
        <RemixCard remix={currentRemix} />
      ) : (
        <div className="text-center py-8">
          <p className="text-gray-400 mb-4">
            Remixが見つかりませんでした。
          </p>
          <button
            onClick={handleBack}
            className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 transition-colors"
          >
            Remix一覧に戻る
          </button>
        </div>
      )}
    </div>
  );
};

export default RemixDetailPage;
