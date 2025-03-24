import { useState, useEffect } from 'react';

/**
 * 値のデバウンス処理を行うカスタムフック
 * 指定した遅延時間後に値を更新する
 * 
 * @param value デバウンス対象の値
 * @param delay 遅延時間（ミリ秒）
 * @returns デバウンスされた値
 */
export function useDebounce<T>(value: T, delay: number): T {
  const [debouncedValue, setDebouncedValue] = useState<T>(value);

  useEffect(() => {
    // 遅延後に値を更新するタイマーをセット
    const timer = setTimeout(() => {
      setDebouncedValue(value);
    }, delay);

    // クリーンアップ関数（コンポーネントのアンマウント時やvalue/delayが変更された時に実行）
    return () => {
      clearTimeout(timer);
    };
  }, [value, delay]);

  return debouncedValue;
}
