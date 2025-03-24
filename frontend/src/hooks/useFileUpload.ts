import { useState, useCallback } from 'react';
import { useMutation } from '@tanstack/react-query';
import apiClient from '../api/client';
import { useToast } from '../context/ToastContext';
import { useNetworkStatus } from './useNetworkStatus';

export interface FileUploadResponse {
  success: boolean;
  message: string;
  bookCount: number;
  highlightCount: number;
}

export interface UploadStats {
  bookCount: number;
  highlightCount: number;
}

/**
 * ファイルアップロード用のカスタムフック
 * 進捗表示、オフライン対応、エラーハンドリングを強化
 */
export const useFileUpload = () => {
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState(false);
  const [uploadStats, setUploadStats] = useState<UploadStats | null>(null);
  const [uploadProgress, setUploadProgress] = useState(0);
  const { showToast } = useToast();
  const { isOnline } = useNetworkStatus();
  
  // ファイルアップロードのミューテーション
  const uploadMutation = useMutation({
    mutationFn: async (formData: FormData) => {
      if (!isOnline) {
        throw new Error('オフラインです。インターネット接続を確認してください。');
      }
      
      const { data } = await apiClient.post<FileUploadResponse>('/api/v2/upload', formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          if (progressEvent.total) {
            const percentCompleted = Math.round((progressEvent.loaded * 100) / progressEvent.total);
            setUploadProgress(percentCompleted);
          }
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
      showToast('success', `${data.bookCount}冊の書籍から${data.highlightCount}件のハイライトを取り込みました。`);
      setFile(null);
      setFilePreview(null);
      setUploadProgress(0);
    },
    onError: (error: Error) => {
      showToast('error', `アップロードエラー: ${error.message}`);
      setUploadProgress(0);
    },
  });

  // ファイル選択ハンドラー
  const handleFileSelect = useCallback((selectedFile: File | null) => {
    if (!selectedFile) {
      setFile(null);
      setFilePreview(null);
      return;
    }

    // ファイル検証
    if (!validateFile(selectedFile)) {
      showToast('error', 'サポートされていないファイル形式です。CSVファイルを選択してください。');
      return;
    }

    setFile(selectedFile);
    setUploadSuccess(false);
    setUploadStats(null);
    setUploadProgress(0);

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
  }, [showToast]);

  // ファイル検証
  const validateFile = (file: File): boolean => {
    // ファイル形式の検証
    if (file.type !== 'text/csv' && !file.name.endsWith('.csv')) {
      return false;
    }
    
    // ファイルサイズの検証（10MB以下）
    if (file.size > 10 * 1024 * 1024) {
      showToast('error', 'ファイルサイズが大きすぎます（上限: 10MB）');
      return false;
    }
    
    return true;
  };

  // ファイルアップロード
  const uploadFile = useCallback(async () => {
    if (!file) {
      showToast('error', 'ファイルが選択されていません');
      return;
    }

    if (!isOnline) {
      showToast('error', 'オフラインです。インターネット接続を確認してください。');
      return;
    }

    const formData = new FormData();
    formData.append('file', file);
    
    try {
      await uploadMutation.mutateAsync(formData);
    } catch (error) {
      console.error('アップロードエラー:', error);
    }
  }, [file, isOnline, showToast, uploadMutation]);

  // ファイルのリセット
  const resetFile = useCallback(() => {
    setFile(null);
    setFilePreview(null);
    setUploadSuccess(false);
    setUploadStats(null);
    setUploadProgress(0);
  }, []);

  return {
    file,
    filePreview,
    uploadSuccess,
    uploadStats,
    uploadProgress,
    isUploading: uploadMutation.isPending,
    error: uploadMutation.error,
    handleFileSelect,
    uploadFile,
    resetFile,
    isOnline
  };
};
