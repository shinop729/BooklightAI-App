import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const Sidebar = () => {
  const { user, login, logout } = useAuth();

  return (
    <aside className="bg-gray-900 text-white w-64 min-h-screen p-4">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-center text-blue-400">Booklight AI</h1>
        <p className="text-sm text-center text-gray-400 mt-1">📚 あなたの読書をAIが照らす</p>
      </div>
      
      <div className="border-t border-gray-700 my-4"></div>
      
      {/* ユーザー情報 */}
      {user ? (
        <div className="mb-6 text-center">
          {user.picture && (
            <img 
              src={user.picture} 
              alt={user.name} 
              className="w-16 h-16 rounded-full mx-auto mb-2"
            />
          )}
          <p className="font-medium">{user.name}</p>
          <p className="text-sm text-gray-400 mb-2">{user.email}</p>
          <button 
            onClick={() => logout()} 
            className="bg-red-600 hover:bg-red-700 text-white px-3 py-1 rounded text-sm w-full"
          >
            ログアウト
          </button>
        </div>
      ) : (
        <div className="mb-6 text-center">
          <p className="text-gray-400 mb-2">ログインしていません</p>
          <button 
            onClick={() => login()} 
            className="bg-blue-600 hover:bg-blue-700 text-white px-3 py-1 rounded w-full"
          >
            ログイン
          </button>
        </div>
      )}
      
      <div className="border-t border-gray-700 my-4"></div>
      
      {/* ナビゲーション */}
      <nav className="space-y-2">
        <Link to="/" className="block py-2 px-4 rounded hover:bg-gray-800">
          🏠 ホーム
        </Link>
        <Link to="/search" className="block py-2 px-4 rounded hover:bg-gray-800">
          🔍 検索モード
        </Link>
        <Link to="/chat" className="block py-2 px-4 rounded hover:bg-gray-800">
          💬 チャットモード
        </Link>
        <Link to="/cross-point" className="block py-2 px-4 rounded hover:bg-gray-800">
          🔄 Cross Point
        </Link>
        <Link to="/books" className="block py-2 px-4 rounded hover:bg-gray-800">
          📚 書籍一覧
        </Link>
        <Link to="/upload" className="block py-2 px-4 rounded hover:bg-gray-800">
          📤 ハイライトアップロード
        </Link>
      </nav>
      
      <div className="border-t border-gray-700 my-4"></div>
      
      {/* サマリー生成進捗（後で実装） */}
      <div className="mt-auto">
        <p className="text-sm text-gray-400">© 2025 Booklight AI</p>
      </div>
    </aside>
  );
};

export default Sidebar;
