import React from 'react';
import { CrossPoint } from '../../types';

interface CrossPointCardProps {
  crossPoint: CrossPoint;
  onLike: (id: number) => void;
  loading?: boolean;
}

/**
 * Cross Pointを表示するカード
 */
const CrossPointCard: React.FC<CrossPointCardProps> = ({ 
  crossPoint, 
  onLike,
  loading = false
}) => {
  const handleLike = () => {
    if (!loading) {
      onLike(crossPoint.id);
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-md overflow-hidden">
      {/* ヘッダー */}
      <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
        <h3 className="text-lg font-semibold text-gray-800 dark:text-white">
          {crossPoint.title}
        </h3>
        <button 
          onClick={handleLike}
          disabled={loading}
          className="text-gray-500 hover:text-red-500 dark:text-gray-400 dark:hover:text-red-400 transition-colors text-xl"
          aria-label={crossPoint.liked ? "お気に入りから削除" : "お気に入りに追加"}
        >
          {crossPoint.liked ? '❤️' : '🤍'}
        </button>
      </div>

      {/* 説明 */}
      <div className="p-4 bg-gray-50 dark:bg-gray-700">
        <p className="text-gray-700 dark:text-gray-300">
          {crossPoint.description}
        </p>
      </div>

      {/* ハイライト */}
      <div className="p-4 space-y-4">
        {crossPoint.highlights.map((highlight, index) => (
          <div key={highlight.id} className="border-l-4 border-blue-500 pl-4 py-2">
            <div className="text-sm text-gray-500 dark:text-gray-400 mb-1">
              『{highlight.book_title}』（{highlight.book_author}）
            </div>
            <blockquote className="text-gray-700 dark:text-gray-300 italic">
              {highlight.content}
            </blockquote>
          </div>
        ))}
      </div>

      {/* フッター */}
      <div className="p-3 bg-gray-50 dark:bg-gray-700 text-right text-xs text-gray-500 dark:text-gray-400">
        {new Date(crossPoint.created_at).toLocaleDateString('ja-JP')}
      </div>
    </div>
  );
};

export default CrossPointCard;
