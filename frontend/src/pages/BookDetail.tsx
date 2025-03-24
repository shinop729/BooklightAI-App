import { useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useBook, useBookHighlights, useFetchCoverImage } from '../hooks/useBooks';
import HighlightCard from '../components/common/HighlightCard';

const BookDetail = () => {
  const { title } = useParams<{ title: string }>();
  const decodedTitle = decodeURIComponent(title || '');
  
  const { data: book, isLoading: isLoadingBook, error: bookError } = useBook(decodedTitle);
  const { data: highlights = [], isLoading: isLoadingHighlights } = useBookHighlights(book?.id || '');
  const { data: coverUrl } = useFetchCoverImage(book?.title || '', book?.author || '');
  
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'location' | 'content'>('location');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // 検索フィルター
  const filteredHighlights = highlights.filter(
    (highlight) => highlight.content.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // ソート
  const sortedHighlights = [...filteredHighlights].sort((a, b) => {
    let comparison = 0;
    
    if (sortBy === 'location') {
      // 位置情報でソート（数値として扱う）
      const locA = parseInt(a.location || '0', 10);
      const locB = parseInt(b.location || '0', 10);
      comparison = locA - locB;
    } else if (sortBy === 'content') {
      // 内容でソート
      comparison = a.content.localeCompare(b.content);
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // ソート切り替え
  const toggleSort = (field: 'location' | 'content') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  // ソートアイコン
  const SortIcon = ({ field }: { field: 'location' | 'content' }) => {
    if (sortBy !== field) return <span className="text-gray-500">⇅</span>;
    return sortOrder === 'asc' ? <span className="text-blue-500">↑</span> : <span className="text-blue-500">↓</span>;
  };

  // ローディング表示
  if (isLoadingBook) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
      </div>
    );
  }

  // エラー表示
  if (bookError || !book) {
    return (
      <div className="max-w-4xl mx-auto px-4 py-8">
        <div className="text-center text-red-500 py-8">
          <p>書籍情報の取得に失敗しました。</p>
          <Link to="/books" className="text-blue-500 hover:underline mt-4 inline-block">
            書籍一覧に戻る
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      {/* 書籍情報 */}
      <div className="flex flex-col md:flex-row gap-6 mb-8">
        {/* 表紙画像 */}
        <div className="w-full md:w-1/3 lg:w-1/4">
          <div className="bg-gray-800 rounded-lg overflow-hidden aspect-w-2 aspect-h-3">
            {coverUrl ? (
              <img
                src={coverUrl}
                alt={`${book.title}の表紙`}
                className="object-cover w-full h-full"
              />
            ) : (
              <div className="flex items-center justify-center w-full h-full text-gray-400">
                表紙なし
              </div>
            )}
          </div>
        </div>
        
        {/* 書籍詳細 */}
        <div className="flex-1">
          <h1 className="text-2xl md:text-3xl font-bold text-white mb-2">{book.title}</h1>
          <p className="text-xl text-gray-300 mb-4">{book.author}</p>
          
          <div className="flex items-center gap-4 mb-4">
            <div className="bg-blue-600 text-white px-3 py-1 rounded-full text-sm">
              {book.highlightCount}件のハイライト
            </div>
            {book.summary && (
              <div className="bg-green-600 text-white px-3 py-1 rounded-full text-sm">
                サマリーあり
              </div>
            )}
          </div>
          
          {book.summary && (
            <div className="mb-6">
              <h2 className="text-xl font-semibold text-white mb-2">サマリー</h2>
              <div className="bg-gray-800 p-4 rounded-lg">
                <p className="text-gray-300 whitespace-pre-wrap">{book.summary}</p>
              </div>
            </div>
          )}
          
          <div className="flex gap-2">
            <Link
              to="/books"
              className="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-white rounded-lg transition-colors"
            >
              書籍一覧に戻る
            </Link>
            <Link
              to="/chat"
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
            >
              この本についてチャットする
            </Link>
          </div>
        </div>
      </div>
      
      {/* ハイライト一覧 */}
      <div>
        <h2 className="text-2xl font-semibold text-white mb-4">ハイライト</h2>
        
        {/* 検索とフィルター */}
        <div className="mb-6">
          <div className="flex flex-col sm:flex-row gap-4 mb-4">
            <div className="flex-1">
              <input
                type="text"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                placeholder="ハイライト内容を検索..."
                className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => toggleSort('location')}
                className={`px-4 py-2 rounded-lg ${
                  sortBy === 'location' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
                }`}
              >
                位置 <SortIcon field="location" />
              </button>
              <button
                onClick={() => toggleSort('content')}
                className={`px-4 py-2 rounded-lg ${
                  sortBy === 'content' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
                }`}
              >
                内容 <SortIcon field="content" />
              </button>
            </div>
          </div>
          <div className="text-gray-400">
            {filteredHighlights.length} 件のハイライトが見つかりました
          </div>
        </div>
        
        {/* ハイライト表示 */}
        {isLoadingHighlights ? (
          <div className="flex justify-center items-center h-40">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : sortedHighlights.length > 0 ? (
          <div className="space-y-4">
            {sortedHighlights.map((highlight, index) => (
              <div key={highlight.id} className="relative">
                <HighlightCard
                  content={highlight.content}
                  title={book.title}
                  author={book.author}
                  index={index}
                />
                {highlight.location && (
                  <div className="absolute top-2 right-2 bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded-full">
                    位置: {highlight.location}
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center text-gray-400 py-8">
            {searchTerm ? (
              <p>検索条件に一致するハイライトが見つかりませんでした。</p>
            ) : (
              <p>この書籍にはハイライトがありません。</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default BookDetail;
