import { useState, useEffect } from 'react';
import { useSearch, SearchResult } from '../hooks/useSearch';
import HighlightCard from '../components/common/HighlightCard';

const Search = () => {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { keywords, results, addKeyword, removeKeyword, clearKeywords, search } = useSearch();

  // 検索実行
  const handleSearch = async () => {
    if (inputValue.trim()) {
      addKeyword(inputValue.trim());
      setInputValue('');
    }
  };

  // キーワード削除
  const handleRemoveKeyword = (keyword: string) => {
    removeKeyword(keyword);
  };

  // キーワード全削除
  const handleClearKeywords = () => {
    clearKeywords();
  };

  // Enterキーで検索実行
  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // キーワードが変更されたら検索実行
  useEffect(() => {
    if (keywords.length > 0) {
      setIsLoading(true);
      search().finally(() => setIsLoading(false));
    }
  }, [keywords, search]);

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-100 mb-6">ハイライト検索</h1>
        
        {/* 検索フォーム */}
        <div className="flex gap-2 mb-4">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="キーワードを入力..."
            className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
          >
            検索
          </button>
        </div>
        
        {/* 選択中のキーワード */}
        {keywords.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {keywords.map((keyword) => (
              <div key={keyword} className="bg-blue-600 text-white px-3 py-1 rounded-full flex items-center">
                <span>{keyword}</span>
                <button
                  onClick={() => handleRemoveKeyword(keyword)}
                  className="ml-2 text-white hover:text-gray-200"
                >
                  ×
                </button>
              </div>
            ))}
            <button
              onClick={handleClearKeywords}
              className="text-gray-400 hover:text-gray-300 text-sm underline"
            >
              すべてクリア
            </button>
          </div>
        )}
      </div>
      
      {/* 検索結果 */}
      <div>
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-xl font-semibold text-white">
            {keywords.length > 0 ? '検索結果' : 'キーワードを入力してください'}
          </h2>
          {results.length > 0 && (
            <span className="text-gray-400">{results.length}件のハイライトが見つかりました</span>
          )}
        </div>
        
        {/* ローディング表示 */}
        {isLoading ? (
          <div className="flex justify-center items-center h-40">
            <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
          </div>
        ) : (
          <div className="space-y-4">
            {results.length > 0 ? (
              results.map((result: SearchResult, index: number) => (
                <div key={index} className="relative">
                  <HighlightCard
                    content={result.doc.page_content}
                    title={result.doc.metadata.original_title}
                    author={result.doc.metadata.original_author}
                    index={index}
                  />
                  {/* スコア表示（オプション） */}
                  <div className="absolute top-2 right-2 bg-blue-600 text-white text-xs px-2 py-1 rounded-full">
                    スコア: {result.score.toFixed(2)}
                  </div>
                </div>
              ))
            ) : keywords.length > 0 ? (
              <div className="text-center text-gray-400 py-8">
                <p>検索結果が見つかりませんでした。</p>
                <p className="text-sm mt-2">別のキーワードで試してみてください。</p>
              </div>
            ) : null}
          </div>
        )}
      </div>
    </div>
  );
};

export default Search;
