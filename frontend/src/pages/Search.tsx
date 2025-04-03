import { useState, useEffect, useRef, useCallback } from 'react';
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
  // シンプル化のため、フィルターオプションを非表示
  const [showFilters, setShowFilters] = useState(false);
  
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
    setSearchOptions,
    clearCache
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

  // キャッシュクリア
  const handleClearCache = useCallback(() => {
    clearCache();
    // 通知表示
    const notification = document.createElement('div');
    notification.className = 'fixed top-4 right-4 bg-blue-600 text-white px-4 py-2 rounded-lg shadow-lg z-50 animate-fade-in-out';
    notification.textContent = 'キャッシュをクリアしました';
    document.body.appendChild(notification);
    
    // 3秒後に通知を削除
    setTimeout(() => {
      notification.classList.add('animate-fade-out');
      setTimeout(() => {
        document.body.removeChild(notification);
      }, 500);
    }, 3000);
  }, [clearCache]);

  // 検索実行
  const handleSearch = async () => {
    if (inputValue.trim()) {
      const keyword = inputValue.trim();
      console.log('検索キーワード追加:', keyword);
      
      // 入力フィールドをクリアしてサジェストを閉じる
      setInputValue('');
      setShowSuggestions(false);
      
      // キーワードを追加（これによりuseEffectが発火して検索が実行される）
      addKeyword(keyword);
      
      // 検索履歴に追加（非同期で行い、UIブロッキングを防止）
      setTimeout(() => {
        if (keywords.length > 0) {
          addToHistory([...keywords, keyword]);
        } else {
          addToHistory([keyword]);
        }
      }, 10);
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
            {/* フィルターボタンは残すが、機能は無効化 */}
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
          
          {/* 検索フィルター（シンプル化のため非表示） */}
          {showFilters && (
            <div className="bg-gray-800 rounded-lg p-4 mt-2 shadow-lg">
              <h3 className="text-white font-medium mb-3">検索オプション</h3>
              <p className="text-gray-400 text-sm">
                現在、検索はキーワードマッチングとFTS（全文検索）を組み合わせた標準モードで動作しています。
                検索オプションはシンプル化のため無効化されています。
              </p>
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
          <div className="flex items-center gap-3">
            {results.length > 0 && (
              <span className="text-gray-400">{results.length}件のハイライトが見つかりました</span>
            )}
            <button
              onClick={handleClearCache}
              className="text-gray-400 hover:text-white text-sm flex items-center"
              title="検索キャッシュをクリア"
            >
              <span className="material-icons text-sm mr-1">cached</span>
              キャッシュクリア
            </button>
          </div>
        </div>
        
        {/* ローディング表示（スケルトンローディング） */}
        {isLoading ? (
          <div className="space-y-4">
            {[...Array(5)].map((_, index) => (
              <div key={index} className="animate-pulse">
                <div className="h-32 bg-gray-700 rounded-lg mb-2 relative overflow-hidden">
                  {/* 波紋エフェクト */}
                  <div className="absolute inset-0 bg-gradient-to-r from-transparent via-gray-600 to-transparent opacity-20" 
                       style={{
                         animation: `shimmer ${1 + index * 0.2}s infinite linear`,
                         backgroundSize: '200% 100%',
                         backgroundPosition: '100% 0'
                       }}></div>
                  {/* コンテンツの模擬表示 */}
                  <div className="p-4">
                    <div className="h-3 bg-gray-600 rounded w-3/4 mb-2"></div>
                    <div className="h-3 bg-gray-600 rounded w-1/2 mb-2"></div>
                    <div className="h-3 bg-gray-600 rounded w-5/6"></div>
                  </div>
                </div>
                <div className="flex justify-between">
                  <div>
                    <div className="h-4 bg-gray-700 rounded w-40 mb-2"></div>
                    <div className="h-3 bg-gray-700 rounded w-24"></div>
                  </div>
                  <div className="h-6 w-16 bg-gray-700 rounded-full"></div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-4">
            {results.length > 0 ? (
              results.map((result: any, index: number) => (
                <div key={index} className="relative">
                  <HighlightCard
                    content={result.content}
                    title={result.book_title}
                    author={result.book_author}
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
