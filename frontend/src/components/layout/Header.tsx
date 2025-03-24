import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useThemeContext } from '../../context/ThemeContext';

const Header = () => {
  const { user, login, logout } = useAuth();
  const { isDarkMode, toggleTheme } = useThemeContext();

  return (
    <header className="bg-gray-800 text-white shadow-md">
      <div className="container mx-auto px-4 py-3 flex justify-between items-center">
        <div className="flex items-center">
          <Link to="/" className="text-xl font-bold">Booklight AI</Link>
          <span className="ml-2 text-sm text-gray-400">📚 あなたの読書をAIが照らす</span>
        </div>
        
        <nav className="hidden md:flex space-x-4">
          <Link to="/" className="hover:text-blue-300">ホーム</Link>
          <Link to="/search" className="hover:text-blue-300">検索</Link>
          <Link to="/chat" className="hover:text-blue-300">チャット</Link>
          <Link to="/books" className="hover:text-blue-300">書籍一覧</Link>
          <Link to="/upload" className="hover:text-blue-300">アップロード</Link>
        </nav>
        
        <div className="flex items-center space-x-4">
          {/* テーマ切り替えボタン */}
          <button
            onClick={toggleTheme}
            className="text-gray-300 hover:text-white focus:outline-none"
            aria-label={isDarkMode ? 'ライトモードに切り替え' : 'ダークモードに切り替え'}
          >
            {isDarkMode ? (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path
                  fillRule="evenodd"
                  d="M10 2a1 1 0 011 1v1a1 1 0 11-2 0V3a1 1 0 011-1zm4 8a4 4 0 11-8 0 4 4 0 018 0zm-.464 4.95l.707.707a1 1 0 001.414-1.414l-.707-.707a1 1 0 00-1.414 1.414zm2.12-10.607a1 1 0 010 1.414l-.706.707a1 1 0 11-1.414-1.414l.707-.707a1 1 0 011.414 0zM17 11a1 1 0 100-2h-1a1 1 0 100 2h1zm-7 4a1 1 0 011 1v1a1 1 0 11-2 0v-1a1 1 0 011-1zM5.05 6.464A1 1 0 106.465 5.05l-.708-.707a1 1 0 00-1.414 1.414l.707.707zm1.414 8.486l-.707.707a1 1 0 01-1.414-1.414l.707-.707a1 1 0 011.414 1.414zM4 11a1 1 0 100-2H3a1 1 0 000 2h1z"
                  clipRule="evenodd"
                ></path>
              </svg>
            ) : (
              <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                <path d="M17.293 13.293A8 8 0 016.707 2.707a8.001 8.001 0 1010.586 10.586z"></path>
              </svg>
            )}
          </button>
          
          {user ? (
            <div className="flex items-center">
              {user.picture && (
                <img 
                  src={user.picture} 
                  alt={user.name} 
                  className="w-8 h-8 rounded-full mr-2"
                />
              )}
              <span className="mr-2 hidden md:inline">{user.name}</span>
              <button 
                onClick={() => logout()} 
                className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm"
              >
                ログアウト
              </button>
            </div>
          ) : (
            <button 
              onClick={() => login()} 
              className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded"
            >
              ログイン
            </button>
          )}
        </div>
      </div>
    </header>
  );
};

export default Header;
