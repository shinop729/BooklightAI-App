import { useState, useEffect, useRef } from 'react';
import { useBooksPagination } from '../hooks/useBooksPagination';
import { Book } from '../types';
import BookCard from '../components/feature/BookCard';

const BookList = () => {
  const [searchInput, setSearchInput] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [pageSizeOption, setPageSizeOption] = useState<number>(12);
  
  // 書籍一覧取得フック
  const {
    books,
    totalItems,
    totalPages,
    currentPage,
    pageSize,
    isLoading,
    error,
    sortBy,
    sortOrder,
    searchTerm,
    goToPage,
    changePageSize,
    changeSort,
    search
  } = useBooksPagination();
  
  // 検索入力のデバウンス処理
  useEffect(() => {
    // 検索語句が変更された場合のみ検索を実行
    if (searchInput !== debouncedSearch) {
      const timer = setTimeout(() => {
        search(searchInput);
        setDebouncedSearch(searchInput);
      }, 300);
      
      return () => clearTimeout(timer);
    }
  }, [searchInput, debouncedSearch]);
  
  // 初回マウント判定用
  const [isInitialMount, setIsInitialMount] = useState(true);
  
  // ページサイズ変更時の処理
  useEffect(() => {
    // コンポーネントの初回マウント時は実行しない
    if (isInitialMount) {
      setIsInitialMount(false);
      return;
    }
    
    // ページサイズが変更された場合のみ実行
    console.log(`ページサイズオプション変更: ${pageSizeOption}`);
    changePageSize(pageSizeOption);
  }, [pageSizeOption, changePageSize]);
  
  // デバッグ用の状態監視
  useEffect(() => {
    console.log('ページネーション状態:', {
      currentPage,
      totalPages,
      itemsCount: books.length,
      isLoading
    });
  }, [currentPage, totalPages, books, isLoading]);

  // ソートアイコン
  const SortIcon = ({ field }: { field: 'title' | 'author' | 'highlightCount' }) => {
    if (sortBy !== field) return <span className="text-gray-500">⇅</span>;
    return sortOrder === 'asc' ? <span className="text-blue-500">↑</span> : <span className="text-blue-500">↓</span>;
  };

  // ページネーションコントロール
  const renderPagination = () => {
    if (totalPages <= 1) return null;
    
    const pageNumbers = [];
    const maxVisiblePages = 5;
    
    // 表示するページ番号の範囲を計算
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    // 表示ページ数が最大数に満たない場合、startPageを調整
    if (endPage - startPage + 1 < maxVisiblePages) {
      startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    // ページ番号リストの生成
    for (let i = startPage; i <= endPage; i++) {
      pageNumbers.push(i);
    }
    
    return (
      <div className="flex justify-center items-center mt-6 space-x-2">
        {/* 最初のページへ */}
        <button
          onClick={() => goToPage(1)}
          disabled={currentPage === 1}
          className={`px-3 py-1 rounded ${
            currentPage === 1
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gray-700 text-white hover:bg-gray-600'
          }`}
        >
          &laquo;
        </button>
        
        {/* 前のページへ */}
        <button
          onClick={() => goToPage(currentPage - 1)}
          disabled={currentPage === 1}
          className={`px-3 py-1 rounded ${
            currentPage === 1
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gray-700 text-white hover:bg-gray-600'
          }`}
        >
          &lt;
        </button>
        
        {/* ページ番号 */}
        {pageNumbers.map(number => (
          <button
            key={number}
            onClick={() => {
              console.log(`ページ${number}ボタンがクリックされました`);
              goToPage(number);
            }}
            className={`px-3 py-1 rounded ${
              currentPage === number
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 text-white hover:bg-gray-600'
            }`}
          >
            {number}
          </button>
        ))}
        
        {/* 次のページへ */}
        <button
          onClick={() => goToPage(currentPage + 1)}
          disabled={currentPage === totalPages}
          className={`px-3 py-1 rounded ${
            currentPage === totalPages
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gray-700 text-white hover:bg-gray-600'
          }`}
        >
          &gt;
        </button>
        
        {/* 最後のページへ */}
        <button
          onClick={() => goToPage(totalPages)}
          disabled={currentPage === totalPages}
          className={`px-3 py-1 rounded ${
            currentPage === totalPages
              ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
              : 'bg-gray-700 text-white hover:bg-gray-600'
          }`}
        >
          &raquo;
        </button>
      </div>
    );
  };
  
  return (
    <div className="max-w-6xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-100 mb-6">書籍一覧</h1>
      
      {/* 検索とフィルター */}
      <div className="mb-6">
        <div className="flex flex-col lg:flex-row gap-4 mb-4">
          <div className="flex-1">
            <input
              type="text"
              value={searchInput}
              onChange={(e) => setSearchInput(e.target.value)}
              placeholder="タイトルまたは著者で検索..."
              className="w-full bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
          <div className="flex flex-wrap gap-2">
            <button
              onClick={() => changeSort('title')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'title' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              タイトル <SortIcon field="title" />
            </button>
            <button
              onClick={() => changeSort('author')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'author' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              著者 <SortIcon field="author" />
            </button>
            <button
              onClick={() => changeSort('highlightCount')}
              className={`px-4 py-2 rounded-lg ${
                sortBy === 'highlightCount' ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300'
              }`}
            >
              ハイライト数 <SortIcon field="highlightCount" />
            </button>
            <select
              value={pageSizeOption}
              onChange={(e) => setPageSizeOption(Number(e.target.value))}
              className="bg-gray-700 text-white px-3 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              <option value={12}>12件/ページ</option>
              <option value={24}>24件/ページ</option>
              <option value={48}>48件/ページ</option>
            </select>
          </div>
        </div>
        <div className="text-gray-400">
          {totalItems} 冊の書籍が見つかりました（{currentPage}/{totalPages}ページ）
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
      ) : books.length > 0 ? (
        <>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {books.map((book: Book) => (
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
          {renderPagination()}
        </>
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
