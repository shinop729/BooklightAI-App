/**
 * 日本語テキストを正規化する関数
 * - 全角/半角の統一
 * - 小文字化
 * - 余分な空白の削除
 */
export const normalizeJapaneseText = (text: string): string => {
  if (!text) return '';
  
  // Unicode正規化（全角/半角の統一）
  let normalized = text.normalize('NFKC');
  
  // 小文字化
  normalized = normalized.toLowerCase();
  
  // 余分な空白の削除（複数の空白を1つにまとめ、前後の空白を削除）
  normalized = normalized.replace(/\s+/g, ' ').trim();
  
  return normalized;
};

/**
 * テキストを指定した長さで切り詰める関数
 */
export const truncateText = (text: string, maxLength: number, suffix: string = '...'): string => {
  if (!text) return '';
  if (text.length <= maxLength) return text;
  
  return text.substring(0, maxLength) + suffix;
};

/**
 * HTMLエスケープ
 */
export const escapeHtml = (text: string): string => {
  if (!text) return '';
  
  const escapeMap: Record<string, string> = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  };
  
  return text.replace(/[&<>"']/g, (match) => escapeMap[match]);
};

/**
 * URLエンコード（日本語対応）
 */
export const encodeJapaneseUri = (text: string): string => {
  if (!text) return '';
  return encodeURIComponent(text);
};
