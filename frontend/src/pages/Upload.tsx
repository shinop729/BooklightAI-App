import { useRef, ChangeEvent } from 'react';
import { useFileUpload } from '../hooks/useFileUpload';
import { useSummaryProgressStore } from '../store/summaryProgressStore';
import { useToast } from '../context/ToastContext';

const Upload = () => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();
  
  // カスタムフックの使用
  const {
    file,
    filePreview,
    uploadSuccess,
    uploadStats,
    uploadProgress,
    isUploading,
    error,
    handleFileSelect,
    uploadFile,
    resetFile,
    isOnline
  } = useFileUpload();
  
  const { 
    isActive: isGenerating, 
    current: completed, 
    total, 
    startProgress: startGenerating 
  } = useSummaryProgressStore();

  // ファイル選択ハンドラー
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    handleFileSelect(selectedFile || null);
  };

  // サマリー生成開始
  const handleGenerateSummaries = () => {
    if (uploadStats?.bookCount) {
      startGenerating(uploadStats.bookCount);
      showToast('info', `${uploadStats.bookCount}冊の書籍のサマリー生成を開始しました`);
    }
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold text-gray-100 mb-6">ハイライトのアップロード</h1>
      
      <div className="bg-gray-800 rounded-lg p-6 shadow-lg mb-8">
        <h2 className="text-xl font-semibold text-white mb-4">CSVファイルをアップロード</h2>
        
        <div className="mb-6">
          <p className="text-gray-300 mb-4">
            KindleのハイライトをCSV形式でアップロードしてください。<br />
            Chrome拡張機能を使用すると、自動的にハイライトを収集できます。
          </p>
          
          {/* オフライン警告 */}
          {!isOnline && (
            <div className="bg-yellow-900/30 border border-yellow-700 rounded-lg p-3 mb-4">
              <p className="text-yellow-400 flex items-center">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5 mr-2" viewBox="0 0 20 20" fill="currentColor">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                オフラインモードです。インターネット接続を確認してください。
              </p>
            </div>
          )}
          
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <input
                type="file"
                ref={fileInputRef}
                onChange={handleFileChange}
                accept=".csv,text/csv"
                className="block w-full text-gray-300 bg-gray-700 rounded-lg cursor-pointer focus:outline-none p-2"
              />
            </div>
            <button
              onClick={uploadFile}
              disabled={!file || isUploading || !isOnline}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isUploading ? '処理中...' : 'アップロード'}
            </button>
          </div>
          
          {/* アップロード進捗バー */}
          {isUploading && uploadProgress > 0 && (
            <div className="mt-4">
              <div className="flex justify-between mb-1 text-sm">
                <span className="text-gray-400">アップロード中...</span>
                <span className="text-blue-400">{uploadProgress}%</span>
              </div>
              <div className="w-full bg-gray-700 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${uploadProgress}%` }}
                ></div>
              </div>
            </div>
          )}
        </div>
        
        {/* ファイルプレビュー */}
        {filePreview && (
          <div className="mb-6">
            <div className="flex justify-between items-center mb-2">
              <h3 className="text-lg font-medium text-white">ファイルプレビュー</h3>
              <button
                onClick={resetFile}
                className="text-gray-400 hover:text-gray-300 text-sm"
              >
                クリア
              </button>
            </div>
            <div className="bg-gray-900 p-4 rounded-lg overflow-x-auto">
              <pre className="text-gray-300 text-sm whitespace-pre-wrap">{filePreview}</pre>
            </div>
            <p className="text-gray-400 text-sm mt-2">※ 最初の10行のみ表示しています</p>
          </div>
        )}
        
        {/* アップロード結果 */}
        {uploadSuccess && uploadStats && (
          <div className="bg-green-900/30 border border-green-700 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-medium text-green-400 mb-2">アップロード成功</h3>
            <p className="text-gray-300">
              {uploadStats.bookCount}冊の書籍から{uploadStats.highlightCount}件のハイライトを取り込みました。
            </p>
            <div className="mt-4">
              <button
                onClick={handleGenerateSummaries}
                disabled={isGenerating}
                className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                書籍サマリーを生成する
              </button>
            </div>
          </div>
        )}
        
        {/* エラー表示 */}
        {error && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-medium text-red-400 mb-2">エラーが発生しました</h3>
            <p className="text-gray-300">
              {error instanceof Error ? error.message : 'ファイルのアップロードに失敗しました。もう一度お試しください。'}
            </p>
          </div>
        )}
      </div>
      
      {/* サマリー生成状況 */}
      {isGenerating && (
        <div className="bg-gray-800 rounded-lg p-6 shadow-lg">
          <h2 className="text-xl font-semibold text-white mb-4">サマリー生成中</h2>
          
          <div className="mb-4">
            <div className="flex justify-between mb-2">
              <span className="text-gray-300">進捗状況</span>
              <span className="text-blue-400">{completed}/{total} 完了</span>
            </div>
            <div className="w-full bg-gray-700 rounded-full h-2.5">
              <div
                className="bg-blue-600 h-2.5 rounded-full transition-all duration-300"
                style={{ width: `${(completed / Math.max(total, 1)) * 100}%` }}
              ></div>
            </div>
          </div>
          
          <p className="text-gray-400 text-sm">
            サマリーの生成には時間がかかる場合があります。このページを閉じても処理は継続されます。
          </p>
        </div>
      )}
    </div>
  );
};

export default Upload;
