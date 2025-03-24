import { useState } from 'react';
import { useBooks, Book } from '../hooks/useBooks';
import BookCard from '../components/feature/BookCard';

const BookList = () => {
  const { data: books = [], isLoading, error } = useBooks();
  const [searchTerm, setSearchTerm] = useState('');
  const [sortBy, setSortBy] = useState<'title' | 'author' | 'highlightCount'>('title');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('asc');

  // 検索フィルター
  const filteredBooks = books.filter(
    (book: Book) =>
      book.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      book.author.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // ソート
  const sortedBooks = [...filteredBooks].sort((a: Book, b: Book) => {
    let comparison = 0;
    
    if (sortBy === 'title') {
      comparison = a.title.localeCompare(b.title);
    } else if (sortBy === 'author') {
      comparison = a.author.localeCompare(b.author);
    } else if (sortBy === 'highlightCount') {
      comparison = a.highlightCount - b.highlightCount;
    }
    
    return sortOrder === 'asc' ? comparison : -comparison;
  });

  // ソート切り替え
  const toggleSort = (field: 'title' | 'author' | 'highlightCount') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('asc');
    }
  };

  // ソートアイコン
  const SortIcon = ({ field }: { field: 'title' | 'author' | 'highlightCount' }) => {
    if (sortBy !== field) return <span className="text-gray-500">⇅</span>;
    return sortOrder === 'asc' ? <span className="text-blue-500">↑</span> : <span className="text-blue-500">↓</span>;
  };

  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-100 mb-6">書籍一覧</h1>
      
      {/* 検索とフィルター */}
      <div className="mb-6">
        <div className="flex flex-col md:flex-row gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              placeholder="タイトルまたは著者で検索..."
              className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => toggleSort('title')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'title' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              タイトル <SortIcon field="title" />
            </button>
            <button
              onClick={() => toggleSort('author')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'author' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              著者 <SortIcon field="author" />
            </button>
            <button
              onClick={() => toggleSort('highlightCount')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'highlightCount' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              ハイライト数 <SortIcon field="highlightCount" />
            </button>
          </div>
        </div>
        <div className="text-gray-400">
          {filteredBooks.length} 冊の書籍が見つかりました
        </div>
      </div>
      
      {/* 書籍一覧 */}
      {isLoading ? (
        <div className="flex justify-center items-center h-64">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      ) : error ? (
        <div className="text-center text-red-500 py-8">
          エラーが発生しました。再読み込みしてください。
        </div>
      ) : sortedBooks.length > 0 ? (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
          {sortedBooks.map((book: Book) => (
            <BookCard
              key={book.id}
              id={book.id}
              title={book.title}
              author={book.author}
              coverUrl={book.coverUrl}
              highlightCount={book.highlightCount}
            />
          ))}
        </div>
      ) : (
        <div className="text-center text-gray-400 py-8">
          {searchTerm ? (
            <p>検索条件に一致する書籍が見つかりませんでした。</p>
          ) : (
            <p>書籍が登録されていません。ハイライトをアップロードしてください。</p>
          )}
        </div>
      )}
    </div>
  );
};

export default BookList;
