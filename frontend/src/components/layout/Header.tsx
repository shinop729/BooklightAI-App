import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const Header = () => {
  const { user, login, logout } = useAuth();

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
        
        <div>
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
