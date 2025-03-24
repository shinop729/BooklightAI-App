import { ReactNode } from 'react';
import Modal from './Modal';
import Button from './Button';

export interface ConfirmDialogProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: string;
  children: ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: 'primary' | 'danger' | 'success' | 'warning';
  isLoading?: boolean;
  size?: 'sm' | 'md' | 'lg' | 'xl';
}

const ConfirmDialog = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  children,
  confirmText = '確認',
  cancelText = 'キャンセル',
  confirmVariant = 'primary',
  isLoading = false,
  size = 'md',
}: ConfirmDialogProps) => {
  // 確認ボタンのクリックハンドラー
  const handleConfirm = () => {
    onConfirm();
    if (!isLoading) {
      onClose();
    }
  };

  // フッターのカスタマイズ
  const footer = (
    <div className="flex justify-end space-x-3">
      <Button variant="secondary" onClick={onClose} disabled={isLoading}>
        {cancelText}
      </Button>
      <Button
        variant={confirmVariant}
        onClick={handleConfirm}
        isLoading={isLoading}
      >
        {confirmText}
      </Button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      footer={footer}
      size={size}
      closeOnClickOutside={!isLoading}
      showCloseButton={!isLoading}
    >
      {children}
    </Modal>
  );
};

export default ConfirmDialog;
