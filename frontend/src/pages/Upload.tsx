import { useState, useRef, ChangeEvent } from 'react';
import { useMutation } from '@tanstack/react-query';
import apiClient from '../api/client';
import { useSummaryProgressStore } from '../store/summaryProgressStore';

interface FileUploadResponse {
  success: boolean;
  message: string;
  bookCount: number;
  highlightCount: number;
}

const Upload = () => {
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadStats, setUploadStats] = useState<{ bookCount: number; highlightCount: number } | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  
  const { isActive: isGenerating, current: completed, total, startProgress: startGenerating } = useSummaryProgressStore();

  // ファイルアップロードのミューテーション
  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      const { data } = await apiClient.post<FileUploadResponse>('/api/v2/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });
      return data;
    },
    onSuccess: (data) => {
      setUploadSuccess(true);
      setUploadStats({
        bookCount: data.bookCount,
        highlightCount: data.highlightCount,
      });
      // ファイル選択をリセット
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    },
  });

  // ファイル選択ハンドラー
  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setFile(selectedFile);
    setUploadSuccess(false);
    setUploadStats(null);

    // CSVファイルのプレビュー
    if (selectedFile.type === 'text/csv' || selectedFile.name.endsWith('.csv')) {
      const reader = new FileReader();
      reader.onload = (event) => {
        const content = event.target?.result as string;
        // 最初の数行だけ表示
        const lines = content.split('\n').slice(0, 10).join('\n');
        setFilePreview(lines);
      };
      reader.readAsText(selectedFile);
    } else {
      setFilePreview(null);
    }
  };

  // ファイルアップロード
  const handleUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    
    try {
      await uploadMutation.mutateAsync(formData);
    } catch (error) {
      console.error('アップロードエラー:', error);
    }
  };

  // サマリー生成開始
  const handleGenerateSummaries = () => {
    if (uploadStats?.bookCount) {
      startGenerating(uploadStats.bookCount);
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
              onClick={handleUpload}
              disabled={!file || uploadMutation.isPending}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {uploadMutation.isPending ? '処理中...' : 'アップロード'}
            </button>
          </div>
        </div>
        
        {/* ファイルプレビュー */}
        {filePreview && (
          <div className="mb-6">
            <h3 className="text-lg font-medium text-white mb-2">ファイルプレビュー</h3>
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
        {uploadMutation.isError && (
          <div className="bg-red-900/30 border border-red-700 rounded-lg p-4 mb-6">
            <h3 className="text-lg font-medium text-red-400 mb-2">エラーが発生しました</h3>
            <p className="text-gray-300">
              ファイルのアップロードに失敗しました。もう一度お試しください。
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
                className="bg-blue-600 h-2.5 rounded-full"
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
