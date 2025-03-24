import { FC } from 'react';
import { useNavigate } from 'react-router-dom';

interface BookCardProps {
  id: string;
  title: string;
  author: string;
  coverUrl?: string;
  highlightCount: number;
}

export const BookCard: FC<BookCardProps> = ({
  id,
  title,
  author,
  coverUrl,
  highlightCount
}) => {
  const navigate = useNavigate();

  const handleClick = () => {
    navigate(`/books/${encodeURIComponent(title)}`);
  };

  return (
    <div className="bg-gray-800 rounded-lg overflow-hidden shadow-lg hover:shadow-xl transition-shadow">
      <div className="aspect-w-2 aspect-h-3 bg-gray-700">
        {coverUrl ? (
          <img
            src={coverUrl}
            alt={`${title}の表紙`}
            className="object-cover w-full h-full"
          />
        ) : (
          <div className="flex items-center justify-center w-full h-full text-gray-400">
            表紙なし
          </div>
        )}
      </div>
      <div className="p-4">
        <h3 className="text-lg font-semibold text-white mb-1 truncate">{title}</h3>
        <p className="text-sm text-gray-400 mb-2">{author}</p>
        <div className="flex justify-between items-center">
          <span className="text-xs text-gray-500">ハイライト {highlightCount}件</span>
          <button
            onClick={handleClick}
            className="px-3 py-1 bg-blue-600 text-white text-sm rounded hover:bg-blue-700 transition-colors"
          >
            詳細
          </button>
        </div>
      </div>
    </div>
  );
};

export default BookCard;
