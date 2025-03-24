import { useEffect, useRef, ReactNode } from 'react';
import { createPortal } from 'react-dom';
import Button from './Button';

export interface ModalProps {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  closeOnClickOutside?: boolean;
  showCloseButton?: boolean;
}

const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md',
  closeOnClickOutside = true,
  showCloseButton = true,
}: ModalProps) => {
  const modalRef = useRef<HTMLDivElement>(null);

  // サイズに基づくスタイル
  const sizeClasses = {
    sm: 'max-w-sm',
    md: 'max-w-md',
    lg: 'max-w-lg',
    xl: 'max-w-xl',
  };

  // ESCキーでモーダルを閉じる
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  // モーダル外のクリックを処理
  const handleBackdropClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (closeOnClickOutside && e.target === e.currentTarget) {
      onClose();
    }
  };

  // モーダルが開いているときは背景のスクロールを無効化
  useEffect(() => {
    if (isOpen) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = '';
    }
    return () => {
      document.body.style.overflow = '';
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black bg-opacity-50 p-4"
      onClick={handleBackdropClick}
    >
      <div
        ref={modalRef}
        className={`${sizeClasses[size]} w-full bg-gray-800 rounded-lg shadow-xl transform transition-all duration-300 ease-in-out ${
          isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95'
        }`}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
      >
        {/* ヘッダー */}
        <div className="flex items-center justify-between p-4 border-b border-gray-700">
          <h3 id="modal-title" className="text-lg font-medium text-white">
            {title}
          </h3>
          {showCloseButton && (
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white focus:outline-none"
              aria-label="閉じる"
            >
              <svg
                className="w-5 h-5"
                fill="currentColor"
                viewBox="0 0 20 20"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  fillRule="evenodd"
                  d="M4.293 4.293a1 1 0 011.414 0L10 8.586l4.293-4.293a1 1 0 111.414 1.414L11.414 10l4.293 4.293a1 1 0 01-1.414 1.414L10 11.414l-4.293 4.293a1 1 0 01-1.414-1.414L8.586 10 4.293 5.707a1 1 0 010-1.414z"
                  clipRule="evenodd"
                ></path>
              </svg>
            </button>
          )}
        </div>

        {/* コンテンツ */}
        <div className="p-4 max-h-[70vh] overflow-y-auto">{children}</div>

        {/* フッター */}
        {footer ? (
          <div className="p-4 border-t border-gray-700">{footer}</div>
        ) : (
          <div className="p-4 border-t border-gray-700 flex justify-end">
            <Button variant="secondary" onClick={onClose}>
              閉じる
            </Button>
          </div>
        )}
      </div>
    </div>,
    document.body
  );
};

export default Modal;
