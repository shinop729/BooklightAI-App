import { useAuth } from '../context/AuthContext';

const Login = () => {
  const { login, loading } = useAuth();

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-900 py-12 px-4 sm:px-6 lg:px-8">
      <main className="max-w-md w-full space-y-8">
        <div>
          <h1 className="text-center text-3xl font-extrabold text-white">Booklight AI</h1>
          <p className="mt-2 text-center text-sm text-gray-400">
            あなたの読書をAIが照らす
          </p>
        </div>
        <div className="mt-8 bg-gray-800 py-8 px-4 shadow rounded-lg sm:px-10">
          <div className="space-y-6">
            <div>
              <p className="text-sm font-medium text-gray-300">
                Booklight AIは、Kindleのハイライト情報を収集・管理し、AI技術を活用してユーザーの読書体験を向上させるアプリケーションです。
              </p>
            </div>
            
            <div className="space-y-2">
              <h2 className="text-lg font-medium text-white">主な機能</h2>
              <ul className="list-disc pl-5 text-sm text-gray-300 space-y-1">
                <li>ハイライト検索</li>
                <li>AIチャット</li>
                <li>書籍サマリー生成</li>
                <li>書籍一覧表示</li>
              </ul>
            </div>
            
            <div>
              <button
                onClick={login}
                disabled={loading}
                className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="flex items-center">
                    <svg className="animate-spin -ml-1 mr-3 h-5 w-5 text-white" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    読み込み中...
                  </span>
                ) : (
                  <span className="flex items-center">
                    <svg className="w-5 h-5 mr-2" viewBox="0 0 24 24" fill="currentColor">
                      <path d="M12.545,10.239v3.821h5.445c-0.712,2.315-2.647,3.972-5.445,3.972c-3.332,0-6.033-2.701-6.033-6.032s2.701-6.032,6.033-6.032c1.498,0,2.866,0.549,3.921,1.453l2.814-2.814C17.503,2.988,15.139,2,12.545,2C7.021,2,2.543,6.477,2.543,12s4.478,10,10.002,10c8.396,0,10.249-7.85,9.426-11.748L12.545,10.239z"/>
                    </svg>
                    Googleでログイン
                  </span>
                )}
              </button>
            </div>
          </div>
        </div>
        
        <div className="mt-6">
          <p className="text-center text-xs text-gray-300">
            &copy; 2025 Booklight AI. All rights reserved.
          </p>
        </div>
      </main>
    </div>
  );
};

export default Login;
