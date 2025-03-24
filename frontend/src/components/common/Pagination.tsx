import { useMemo } from 'react';

export interface PaginationProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
  siblingCount?: number;
}

const Pagination = ({
  currentPage,
  totalPages,
  onPageChange,
  siblingCount = 1,
}: PaginationProps) => {
  // ページ番号の配列を生成
  const paginationRange = useMemo(() => {
    // 表示するページ番号の最大数
    const totalPageNumbers = siblingCount * 2 + 3; // 前後のsiblingCount + 現在のページ + 最初と最後のページ

    // 総ページ数が表示可能な最大数以下の場合、すべてのページを表示
    if (totalPageNumbers >= totalPages) {
      return Array.from({ length: totalPages }, (_, i) => i + 1);
    }

    // 左右のsiblingの開始と終了のインデックス
    const leftSiblingIndex = Math.max(currentPage - siblingCount, 1);
    const rightSiblingIndex = Math.min(currentPage + siblingCount, totalPages);

    // 省略記号を表示するかどうか
    const shouldShowLeftDots = leftSiblingIndex > 2;
    const shouldShowRightDots = rightSiblingIndex < totalPages - 1;

    // 最初のページと最後のページは常に表示
    const firstPageIndex = 1;
    const lastPageIndex = totalPages;

    // 左側の省略記号のみを表示する場合
    if (!shouldShowLeftDots && shouldShowRightDots) {
      const leftItemCount = 3 + 2 * siblingCount;
      const leftRange = Array.from({ length: leftItemCount }, (_, i) => i + 1);
      return [...leftRange, '...', totalPages];
    }

    // 右側の省略記号のみを表示する場合
    if (shouldShowLeftDots && !shouldShowRightDots) {
      const rightItemCount = 3 + 2 * siblingCount;
      const rightRange = Array.from(
        { length: rightItemCount },
        (_, i) => totalPages - rightItemCount + i + 1
      );
      return [firstPageIndex, '...', ...rightRange];
    }

    // 両側に省略記号を表示する場合
    if (shouldShowLeftDots && shouldShowRightDots) {
      const middleRange = Array.from(
        { length: rightSiblingIndex - leftSiblingIndex + 1 },
        (_, i) => leftSiblingIndex + i
      );
      return [firstPageIndex, '...', ...middleRange, '...', lastPageIndex];
    }

    return [];
  }, [totalPages, currentPage, siblingCount]);

  // ページが1ページしかない場合は表示しない
  if (totalPages <= 1) return null;

  return (
    <nav className="flex justify-center mt-6" aria-label="ページネーション">
      <ul className="flex space-x-1">
        {/* 前のページボタン */}
        <li>
          <button
            onClick={() => onPageChange(currentPage - 1)}
            disabled={currentPage === 1}
            className={`px-3 py-1 rounded-md ${
              currentPage === 1
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-gray-700 text-white hover:bg-gray-600'
            }`}
            aria-label="前のページ"
          >
            &laquo;
          </button>
        </li>

        {/* ページ番号 */}
        {paginationRange.map((pageNumber, index) => {
          if (pageNumber === '...') {
            return (
              <li key={`ellipsis-${index}`}>
                <span className="px-3 py-1 bg-gray-700 text-gray-400">...</span>
              </li>
            );
          }

          return (
            <li key={`page-${pageNumber}`}>
              <button
                onClick={() => onPageChange(pageNumber as number)}
                className={`px-3 py-1 rounded-md ${
                  pageNumber === currentPage
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-white hover:bg-gray-600'
                }`}
                aria-current={pageNumber === currentPage ? 'page' : undefined}
              >
                {pageNumber}
              </button>
            </li>
          );
        })}

        {/* 次のページボタン */}
        <li>
          <button
            onClick={() => onPageChange(currentPage + 1)}
            disabled={currentPage === totalPages}
            className={`px-3 py-1 rounded-md ${
              currentPage === totalPages
                ? 'bg-gray-700 text-gray-500 cursor-not-allowed'
                : 'bg-gray-700 text-white hover:bg-gray-600'
            }`}
            aria-label="次のページ"
          >
            &raquo;
          </button>
        </li>
      </ul>
    </nav>
  );
};

export default Pagination;
