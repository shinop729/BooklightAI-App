import React from 'react';
import { Remix } from '../../types/remix';
import { Link } from 'react-router-dom';

interface RemixCardProps {
  remix: Remix;
  isPreview?: boolean;
}

/**
 * Remixを表示するカード
 */
const RemixCard: React.FC<RemixCardProps> = ({ 
  remix,
  isPreview = false
}) => {
  // プレビュー用に内容を短縮
  const previewContent = isPreview 
    ? remix.content.substring(0, 200) + (remix.content.length > 200 ? '...' : '')
    : remix.content;

  return (
    <div className="bg-gray-800 rounded-lg shadow-md overflow-hidden">
      {/* ヘッダー */}
      <div className="p-4 border-b border-gray-700">
        <h3 className="text-lg font-semibold text-white">
          {remix.title}
        </h3>
        <div className="text-sm text-gray-400 mt-1">
          テーマ: {remix.theme}
        </div>
      </div>

      {/* コンテンツ */}
      <div className="p-4">
        <div className="prose prose-invert max-w-none">
          {isPreview ? (
            <>
              <p className="text-gray-300">{previewContent}</p>
              <Link to={`/remix/${remix.id}`} className="text-blue-400 hover:text-blue-300">
                続きを読む
              </Link>
            </>
          ) : (
            <div 
              className="text-gray-300"
              dangerouslySetInnerHTML={{ __html: remix.content.replace(/\n/g, '<br>') }}
            />
          )}
        </div>
      </div>

      {/* 使用ハイライト */}
      {!isPreview && (
        <div className="p-4 border-t border-gray-700">
          <h4 className="text-md font-medium text-white mb-2">
            使用ハイライト
          </h4>
          <div className="space-y-3">
            {remix.highlights.map((highlight) => (
              <div key={highlight.id} className="border-l-4 border-blue-500 pl-3 py-1">
                <div className="text-sm text-gray-400 mb-1">
                  『{highlight.book_title}』（{highlight.book_author}）
                </div>
                <blockquote className="text-gray-300 text-sm italic">
                  {highlight.content}
                </blockquote>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* フッター */}
      <div className="p-3 bg-gray-700 text-right text-xs text-gray-400">
        {new Date(remix.created_at).toLocaleDateString('ja-JP')}
      </div>
    </div>
  );
};

export default RemixCard;
