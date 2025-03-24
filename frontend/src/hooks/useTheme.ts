import { useEffect } from 'react';
import useLocalStorage from './useLocalStorage';

type Theme = 'light' | 'dark' | 'system';

interface UseThemeReturn {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  isDarkMode: boolean;
  toggleTheme: () => void;
}

const useTheme = (): UseThemeReturn => {
  // テーマの状態をlocalStorageに保存
  const [theme, setTheme] = useLocalStorage<Theme>('booklight-theme', 'system');
  
  // システムのダークモード設定を取得
  const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  
  // 現在のテーマがダークモードかどうか
  const isDarkMode = theme === 'dark' || (theme === 'system' && systemPrefersDark);

  // テーマの切り替え
  const toggleTheme = () => {
    if (theme === 'dark') {
      setTheme('light');
    } else {
      setTheme('dark');
    }
  };

  // テーマに基づいてHTMLのdata-theme属性を設定
  useEffect(() => {
    const root = window.document.documentElement;
    
    if (isDarkMode) {
      root.classList.add('dark');
      root.classList.remove('light');
    } else {
      root.classList.add('light');
      root.classList.remove('dark');
    }
  }, [isDarkMode]);

  // システムのテーマ変更を監視
  useEffect(() => {
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
    
    const handleChange = () => {
      // テーマが'system'の場合のみ再レンダリングが必要
      if (theme === 'system') {
        // 強制的に再レンダリングするためにテーマを一時的に変更して戻す
        setTheme('system');
      }
    };
    
    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [theme, setTheme]);

  return { theme, setTheme, isDarkMode, toggleTheme };
};

export default useTheme;
