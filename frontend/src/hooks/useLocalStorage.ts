import { useState, useEffect } from 'react';

type SetValue<T> = T | ((val: T) => T);

function useLocalStorage<T>(
  key: string,
  initialValue: T
): [T, (value: SetValue<T>) => void] {
  // 初期値の取得
  const readValue = (): T => {
    // SSRの場合はlocalStorageが存在しないため、初期値を返す
    if (typeof window === 'undefined') {
      return initialValue;
    }

    try {
      // localStorageから値を取得
      const item = window.localStorage.getItem(key);
      // 値が存在する場合はパースして返す、存在しない場合は初期値を返す
      return item ? (JSON.parse(item) as T) : initialValue;
    } catch (error) {
      console.warn(`Error reading localStorage key "${key}":`, error);
      return initialValue;
    }
  };

  // 状態の初期化
  const [storedValue, setStoredValue] = useState<T>(readValue);

  // 値を設定する関数
  const setValue = (value: SetValue<T>) => {
    try {
      // 新しい値を計算（関数または値）
      const newValue = value instanceof Function ? value(storedValue) : value;
      
      // localStorageに保存
      if (typeof window !== 'undefined') {
        window.localStorage.setItem(key, JSON.stringify(newValue));
      }
      
      // 状態を更新
      setStoredValue(newValue);
      
      // 変更イベントを発火（他のコンポーネントに通知）
      window.dispatchEvent(new Event('local-storage'));
    } catch (error) {
      console.warn(`Error setting localStorage key "${key}":`, error);
    }
  };

  // 他のコンポーネントからの変更を監視
  useEffect(() => {
    const handleStorageChange = () => {
      setStoredValue(readValue());
    };
    
    // ストレージ変更イベントをリッスン
    window.addEventListener('storage', handleStorageChange);
    window.addEventListener('local-storage', handleStorageChange);
    
    // クリーンアップ
    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('local-storage', handleStorageChange);
    };
  }, [key, readValue]);

  return [storedValue, setValue];
}

export default useLocalStorage;
