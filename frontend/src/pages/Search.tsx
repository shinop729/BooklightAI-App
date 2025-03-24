import { useState, useEffect, useRef } from 'react';
import { useSearch } from '../hooks/useSearch';
import { useSearchSuggest } from '../hooks/useSearchSuggest';
import { useSearchHistory } from '../hooks/useSearchHistory';
import { SearchResult } from '../types';
import HighlightCard from '../components/common/HighlightCard';
import { formatDate } from '../utils/textUtils';

const Search = () => {
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [showFilters, setShowFilters] = useState(false);
  const [hybridAlpha, setHybridAlpha] = useState(0.7); // ベクトル検索の重み（0-1）
  const [bookWeight, setBookWeight] = useState(0.3); // 書籍情報の重み（0-1）
  const [useExpanded, setUseExpanded] = useState(true); // 拡張検索の使用
  
  const suggestionsRef = useRef<HTMLDivElement>(null);
  const historyRef = useRef<HTMLDivElement>(null);
  
  // 検索フック
  const { 
    keywords, 
    results, 
    addKeyword, 
    removeKeyword, 
    clearKeywords, 
    search,
    setSearchOptions
  } = useSearch();
  
  // 検索サジェストフック
  const { suggestions, isLoading: isSuggestLoading } = useSearchSuggest(inputValue);
  
  // 検索履歴フック
  const { 
    history, 
    isLoading: isHistoryLoading, 
    addToHistory, 
    deleteFromHistory, 
    clearHistory 
  } = useSearchHistory();
  
  // 検索オプションの更新
  useEffect(() => {
    setSearchOptions({
      hybrid_alpha: hybridAlpha,
      book_weight: bookWeight,
      use_expanded: useExpanded
    });
  }, [hybridAlpha, bookWeight, useExpanded, setSearchOptions]);
  
  // クリック外れ検出用のイベントリスナー
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      // サジェスト領域外のクリックでサジェストを閉じる
      if (
        suggestionsRef.current && 
        !suggestionsRef.current.contains(event.target as Node)
      ) {
        setShowSuggestions(false);
      }
      
      // 履歴領域外のクリックで履歴を閉じる
      if (
        historyRef.current && 
        !historyRef.current.contains(event.target as Node)
      ) {
        setShowHistory(false);
      }
    };
    
    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  // 検索実行
  const handleSearch = async () => {
    if (inputValue.trim()) {
      const keyword = inputValue.trim();
      addKeyword(keyword);
      setInputValue('');
      setShowSuggestions(false);
      
      // 検索履歴に追加
      if (keywords.length > 0) {
        addToHistory([...keywords, keyword]);
      } else {
        addToHistory([keyword]);
      }
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
    } else if (e.key === 'ArrowDown' && showSuggestions && suggestions.length > 0) {
      // 下矢印キーでサジェストにフォーカス
      const suggestionElements = document.querySelectorAll('.suggestion-item');
      if (suggestionElements.length > 0) {
        (suggestionElements[0] as HTMLElement).focus();
      }
    }
  };
  
  // サジェスト選択
  const handleSelectSuggestion = (suggestion: string) => {
    setInputValue(suggestion);
    setShowSuggestions(false);
  };
  
  // 履歴アイテム選択
  const handleSelectHistoryItem = (keywords: string[]) => {
    clearKeywords();
    keywords.forEach(keyword => addKeyword(keyword));
    setShowHistory(false);
  };
  
  // 履歴アイテム削除
  const handleDeleteHistoryItem = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    deleteFromHistory(id);
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
        <div className="relative">
          <div className="flex gap-2 mb-4">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setShowSuggestions(true)}
              placeholder="キーワードを入力..."
              className="flex-1 bg-gray-700 text-white px-4 py-2 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <button
              onClick={handleSearch}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              検索
            </button>
            <button
              onClick={() => setShowHistory(!showHistory)}
              className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-2 rounded-lg transition-colors"
              title="検索履歴"
            >
              <span className="material-icons">history</span>
            </button>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className="bg-gray-600 hover:bg-gray-700 text-white px-3 py-2 rounded-lg transition-colors"
              title="検索オプション"
            >
              <span className="material-icons">tune</span>
            </button>
          </div>
          
          {/* 検索サジェスト */}
          {showSuggestions && inputValue.length >= 2 && (
            <div 
              ref={suggestionsRef}
              className="absolute z-10 w-full bg-gray-800 rounded-lg shadow-lg mt-1 max-h-60 overflow-y-auto"
            >
              {isSuggestLoading ? (
                <div className="p-3 text-gray-400 text-center">
                  <div className="inline-block animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-blue-500 mr-2"></div>
                  候補を読み込み中...
                </div>
              ) : suggestions.length > 0 ? (
                <ul>
                  {suggestions.map((suggestion, index) => (
                    <li 
                      key={index}
                      className="suggestion-item px-4 py-2 hover:bg-gray-700 cursor-pointer focus:bg-gray-700 focus:outline-none"
                      onClick={() => handleSelectSuggestion(suggestion)}
                      tabIndex={0}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') handleSelectSuggestion(suggestion);
                        else if (e.key === 'ArrowDown' && index < suggestions.length - 1) {
                          e.preventDefault();
                          const nextElement = document.querySelectorAll('.suggestion-item')[index + 1] as HTMLElement;
                          if (nextElement) nextElement.focus();
                        }
                        else if (e.key === 'ArrowUp') {
                          e.preventDefault();
                          if (index > 0) {
                            const prevElement = document.querySelectorAll('.suggestion-item')[index - 1] as HTMLElement;
                            if (prevElement) prevElement.focus();
                          } else {
                            const inputElement = document.querySelector('input[type="text"]') as HTMLElement;
                            if (inputElement) inputElement.focus();
                          }
                        }
                      }}
                    >
                      {suggestion}
                    </li>
                  ))}
                </ul>
              ) : inputValue.length >= 2 ? (
                <div className="p-3 text-gray-400 text-center">
                  候補はありません
                </div>
              ) : null}
            </div>
          )}
          
          {/* 検索履歴 */}
          {showHistory && (
            <div 
              ref={historyRef}
              className="absolute z-10 right-0 w-96 bg-gray-800 rounded-lg shadow-lg mt-1 max-h-96 overflow-y-auto"
            >
              <div className="flex justify-between items-center p-3 border-b border-gray-700">
                <h3 className="text-white font-medium">検索履歴</h3>
                <button
                  onClick={() => clearHistory()}
                  className="text-gray-400 hover:text-gray-300 text-sm"
                  disabled={isHistoryLoading}
                >
                  すべて削除
                </button>
              </div>
              
              {isHistoryLoading ? (
                <div className="p-4 text-center">
                  <div className="inline-block animate-spin rounded-full h-5 w-5 border-t-2 border-b-2 border-blue-500 mr-2"></div>
                  読み込み中...
                </div>
              ) : history.length > 0 ? (
                <ul>
                  {history.map((item) => (
                    <li 
                      key={item.id}
                      className="px-4 py-3 hover:bg-gray-700 cursor-pointer border-b border-gray-700 last:border-b-0"
                      onClick={() => handleSelectHistoryItem(item.keywords)}
                    >
                      <div className="flex justify-between items-start">
                        <div>
                          <div className="text-white mb-1">
                            {item.keywords.join(', ')}
                          </div>
                          <div className="text-gray-400 text-xs">
                            {formatDate(item.timestamp)} · {item.result_count}件の結果
                          </div>
                        </div>
                        <button
                          onClick={(e) => handleDeleteHistoryItem(e, item.id)}
                          className="text-gray-400 hover:text-gray-300"
                        >
                          ×
                        </button>
                      </div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="p-4 text-center text-gray-400">
                  検索履歴はありません
                </div>
              )}
            </div>
          )}
          
          {/* 検索フィルター */}
          {showFilters && (
            <div className="bg-gray-800 rounded-lg p-4 mt-2 shadow-lg">
              <h3 className="text-white font-medium mb-3">検索オプション</h3>
              
              <div className="space-y-4">
                <div>
                  <label className="block text-gray-400 mb-1 text-sm">
                    ベクトル検索の重み: {hybridAlpha.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={hybridAlpha}
                    onChange={(e) => setHybridAlpha(parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>キーワード重視</span>
                    <span>意味重視</span>
                  </div>
                </div>
                
                <div>
                  <label className="block text-gray-400 mb-1 text-sm">
                    書籍情報の重み: {bookWeight.toFixed(1)}
                  </label>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.1"
                    value={bookWeight}
                    onChange={(e) => setBookWeight(parseFloat(e.target.value))}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>内容重視</span>
                    <span>書籍重視</span>
                  </div>
                </div>
                
                <div className="flex items-center">
                  <input
                    type="checkbox"
                    id="useExpanded"
                    checked={useExpanded}
                    onChange={(e) => setUseExpanded(e.target.checked)}
                    className="mr-2"
                  />
                  <label htmlFor="useExpanded" className="text-gray-400 text-sm">
                    拡張検索を使用（類似語も検索）
                  </label>
                </div>
              </div>
            </div>
          )}
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
