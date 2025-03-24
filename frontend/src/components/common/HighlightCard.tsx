import { Link } from 'react-router-dom';

interface HighlightCardProps {
  content: string;
  title: string;
  author: string;
  index?: number;
}

const HighlightCard = ({ content, title, author, index = 0 }: HighlightCardProps) => {
  // URLエンコードされたタイトル
  const encodedTitle = encodeURIComponent(title);
  
  return (
    <div className="mb-4">
      <div className="p-4 rounded-lg bg-gray-800 shadow-md">
        <p className="text-white text-base leading-relaxed mb-3">{content}</p>
      </div>
      
      <Link 
        to={`/books/${encodedTitle}`}
        className="mt-2 inline-block w-full py-2 px-4 bg-gray-700 hover:bg-gray-600 text-white rounded text-center transition-colors"
      >
        📚 {title} / {author}
      </Link>
    </div>
  );
};

export default HighlightCard;
