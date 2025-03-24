import { useState, useEffect, ReactNode } from 'react';
import { createPortal } from 'react-dom';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastProps {
  type: ToastType;
  message: string;
  duration?: number;
  onClose?: () => void;
  icon?: ReactNode;
}

const Toast = ({ type, message, duration = 3000, onClose, icon }: ToastProps) => {
  const [isVisible, setIsVisible] = useState(true);
  const [progress, setProgress] = useState(100);

  // トーストのスタイル
  const typeStyles = {
    success: 'bg-green-600 border-green-700',
    error: 'bg-red-600 border-red-700',
    info: 'bg-blue-600 border-blue-700',
    warning: 'bg-yellow-600 border-yellow-700',
  };

  // デフォルトアイコン
  const defaultIcons = {
    success: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clipRule="evenodd"></path>
      </svg>
    ),
    error: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd"></path>
      </svg>
    ),
    info: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-11a1 1 0 10-2 0v4a1 1 0 102 0V7zm-1-5a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd"></path>
      </svg>
    ),
    warning: (
      <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
        <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-7a1 1 0 10-2 0v3a1 1 0 102 0v-3zm-1-5a1 1 0 100 2 1 1 0 000-2z" clipRule="evenodd"></path>
      </svg>
    ),
  };

  // 自動的に閉じる
  useEffect(() => {
    if (duration === 0) return;

    const timer = setTimeout(() => {
      setIsVisible(false);
    }, duration);

    // プログレスバーのアニメーション
    const interval = setInterval(() => {
      setProgress((prev) => {
        const newProgress = prev - (100 / (duration / 100));
        return newProgress < 0 ? 0 : newProgress;
      });
    }, 100);

    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [duration]);

  // 非表示になった後にコンポーネントを削除
  useEffect(() => {
    if (!isVisible && onClose) {
      const timer = setTimeout(() => {
        onClose();
      }, 300); // アニメーション時間

      return () => clearTimeout(timer);
    }
  }, [isVisible, onClose]);

  // ポータルを使用してトーストをbody直下に配置
  return createPortal(
    <div
      className={`fixed top-4 right-4 z-50 max-w-md transform transition-transform duration-300 ${
        isVisible ? 'translate-x-0' : 'translate-x-full'
      }`}
    >
      <div
        className={`${typeStyles[type]} text-white p-4 rounded-lg shadow-lg border-l-4 flex items-start`}
      >
        <div className="flex-shrink-0 mr-3">
          {icon || defaultIcons[type]}
        </div>
        <div className="flex-1">
          <p className="text-sm font-medium">{message}</p>
          {duration > 0 && (
            <div className="w-full bg-gray-200 bg-opacity-30 h-1 mt-2 rounded-full overflow-hidden">
              <div
                className="h-full bg-white rounded-full"
                style={{ width: `${progress}%`, transition: 'width 100ms linear' }}
              ></div>
            </div>
          )}
        </div>
        <button
          onClick={() => setIsVisible(false)}
          className="ml-4 text-white hover:text-gray-200 focus:outline-none"
        >
          <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
            <path
              fillRule="evenodd"
              d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
              clipRule="evenodd"
            ></path>
          </svg>
        </button>
      </div>
    </div>,
    document.body
  );
};

export default Toast;
